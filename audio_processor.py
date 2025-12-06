"""
Audio Processing Module
Handles voice message transcription (STT) and text-to-speech (TTS)
"""
import base64
import tempfile
import os
import requests
from typing import Optional
from openai import OpenAI
from app_logger import logger
from config import OPENAI_API_KEY, SERIES_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

# Try to import pydub for audio conversion (optional)
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available - audio conversion will be limited")

# Supported audio formats
AUDIO_MIME_TYPES = [
    'audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/m4a',
    'audio/wav', 'audio/webm', 'audio/ogg', 'audio/aac',
    'audio/x-m4a', 'audio/quicktime'
]


def is_audio_attachment(attachment: dict) -> bool:
    """
    Check if an attachment is an audio/voice message
    
    Args:
        attachment: Attachment dict with mime_type
        
    Returns:
        bool: True if it's an audio file
    """
    mime_type = attachment.get('mime_type', '').lower()
    return any(audio_type in mime_type for audio_type in ['audio/', 'video/']) or \
           attachment.get('filename', '').lower().endswith(('.mp3', '.m4a', '.wav', '.webm', '.ogg', '.aac'))


def transcribe_audio(base64_data: str, mime_type: str = 'audio/m4a') -> Optional[str]:
    """
    Transcribe audio to text using OpenAI Whisper
    
    Args:
        base64_data: Base64-encoded audio data (no data URI prefix)
        mime_type: MIME type of the audio file
        
    Returns:
        str: Transcribed text, or None if failed
    """
    try:
        # Decode base64 data
        audio_bytes = base64.b64decode(base64_data)
        
        # Normalize mime types - OpenAI Whisper expects specific formats
        # Map common variations to standard formats
        mime_normalization = {
            'audio/mp3': 'audio/mpeg',  # Normalize mp3 to mpeg
            'audio/x-m4a': 'audio/m4a',
            'audio/quicktime': 'audio/m4a',
        }
        normalized_mime = mime_normalization.get(mime_type.lower(), mime_type.lower())
        
        # Create a temporary file
        # Determine file extension from normalized mime_type
        ext_map = {
            'audio/mpeg': '.mp3',
            'audio/mp3': '.mp3',
            'audio/mp4': '.m4a',
            'audio/m4a': '.m4a',
            'audio/x-m4a': '.m4a',
            'audio/quicktime': '.m4a',
            'audio/wav': '.wav',
            'audio/webm': '.webm',
            'audio/ogg': '.ogg',
            'audio/aac': '.aac'
        }
        
        extension = ext_map.get(normalized_mime, '.m4a')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        # Verify file was written correctly
        file_size = os.path.getsize(temp_file_path)
        logger.debug(f"📁 Created temp file: {temp_file_path}, size: {file_size} bytes")
        
        if file_size == 0:
            logger.error("[ERROR] Audio file is empty (0 bytes)")
            try:
                os.unlink(temp_file_path)
            except:
                pass
            return None
        
        # Try multiple strategies to transcribe
        strategies = [
            # Strategy 1: Try with original file
            (temp_file_path, extension, "original file"),
            # Strategy 2: Try as different formats if first fails
            (temp_file_path, '.mp3', "as MP3"),
            (temp_file_path, '.m4a', "as M4A"),
            (temp_file_path, '.wav', "as WAV"),
        ]
        
        last_error = None
        created_files = [temp_file_path]  # Track all files we create for cleanup
        
        for file_path, file_ext, strategy_name in strategies:
            try:
                # For strategies 2+, create a copy with different extension
                if file_ext != extension:
                    alt_path = temp_file_path.rsplit('.', 1)[0] + file_ext
                    try:
                        with open(temp_file_path, 'rb') as src, open(alt_path, 'wb') as dst:
                            dst.write(src.read())
                        file_path = alt_path
                        created_files.append(alt_path)  # Track for cleanup
                    except Exception as copy_err:
                        logger.debug(f"Could not create {file_ext} copy: {copy_err}")
                        continue
                
                # Transcribe using OpenAI Whisper
                logger.info(f"Transcribing audio file: {file_path} ({len(audio_bytes)} bytes, mime: {normalized_mime}, strategy: {strategy_name})")
                
                try:
                    with open(file_path, 'rb') as audio_file:
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language=None,  # Auto-detect
                            response_format="text"
                        )
                    
                    logger.debug(f"[DEBUG] Raw transcript type: {type(transcript)}, value: {repr(transcript)}")
                    transcribed_text = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
                    logger.debug(f"[DEBUG] After strip: {repr(transcribed_text)}, length: {len(transcribed_text)}")
                    
                    if transcribed_text:
                        logger.info(f"[OK] Transcribed audio: {transcribed_text[:100]}...")
                        # Clean up any alternate files
                        if file_path != temp_file_path and os.path.exists(file_path):
                            try:
                                os.unlink(file_path)
                            except:
                                pass
                        return transcribed_text
                    else:
                        logger.warning(f"[WARN]  Transcription returned empty string - audio might be silent or unclear")
                        continue
                        
                except Exception as whisper_error:
                    error_str = str(whisper_error)
                    # Check if it's a format error
                    if "Invalid file format" in error_str or "400" in error_str:
                        logger.debug(f"[WARN]  Whisper rejected {strategy_name}: {error_str[:200]}")
                        last_error = whisper_error
                        continue
                    else:
                        # Other errors, log and continue to next strategy
                        logger.debug(f"[WARN]  Whisper error with {strategy_name}: {error_str[:200]}")
                        last_error = whisper_error
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with strategy {strategy_name}: {e}")
                last_error = e
                continue
        
        # If all direct strategies failed, try pydub conversion (if available and ffmpeg is installed)
        logger.warning(f"[WARN]  All direct transcription attempts failed. Attempting audio conversion...")
        
        if PYDUB_AVAILABLE:
            try:
                # Check if ffmpeg/ffprobe is available by trying to use pydub
                # pydub will raise an error if ffmpeg is not found
                try:
                    audio = AudioSegment.from_file(temp_file_path)
                    # Convert to WAV (most compatible format)
                    wav_path = temp_file_path.rsplit('.', 1)[0] + '.wav'
                    audio.export(wav_path, format="wav")
                    created_files.append(wav_path)  # Track for cleanup
                    logger.info(f"[OK] Converted to WAV: {wav_path}")
                    
                    # Try transcribing the converted file
                    with open(wav_path, 'rb') as wav_file:
                        wav_size = os.path.getsize(wav_path)
                        logger.debug(f"📁 WAV file size: {wav_size} bytes")
                        
                        if wav_size == 0:
                            logger.warning("[WARN]  Converted WAV file is empty")
                            try:
                                os.unlink(wav_path)
                            except:
                                pass
                            raise Exception("Converted file is empty")
                        
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=wav_file,
                            language=None,
                            response_format="text"
                        )
                    
                    logger.debug(f"[DEBUG] Raw transcript type: {type(transcript)}, value: {repr(transcript)}")
                    transcribed_text = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
                    logger.debug(f"[DEBUG] After strip: {repr(transcribed_text)}, length: {len(transcribed_text)}")
                    
                    # Clean up converted file
                    try:
                        os.unlink(wav_path)
                    except:
                        pass
                    
                    if transcribed_text:
                        logger.info(f"[OK] Transcribed converted audio: {transcribed_text[:100]}...")
                        return transcribed_text
                    else:
                        logger.warning(f"[WARN]  Transcription returned empty string after conversion")
                        return None
                        
                except FileNotFoundError as ffmpeg_error:
                    logger.warning(f"[WARN]  ffmpeg/ffprobe not found. Audio conversion unavailable. Install ffmpeg or add it to PATH.")
                    logger.warning(f"   Error: {ffmpeg_error}")
                    # Continue to final cleanup
                except Exception as convert_error:
                    logger.error(f"[ERROR] Audio conversion failed: {convert_error}")
                    # Continue to final cleanup
            except Exception as pydub_error:
                logger.warning(f"[WARN]  pydub conversion failed: {pydub_error}")
        else:
            logger.warning("[WARN]  pydub not available for audio conversion")
        
        # All strategies failed
        if last_error:
            logger.error(f"[ERROR] All transcription strategies failed. Last error: {last_error}")
        else:
            logger.error(f"[ERROR] All transcription strategies failed (no specific error captured)")
        
        return None
            
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}", exc_info=True)
        return None
    finally:
        # Clean up all created temp files
        if 'created_files' in locals():
            for file_to_clean in created_files:
                try:
                    if os.path.exists(file_to_clean):
                        os.unlink(file_to_clean)
                except Exception as cleanup_err:
                    logger.debug(f"Could not clean up {file_to_clean}: {cleanup_err}")
        elif 'temp_file_path' in locals():
            # Fallback if created_files wasn't initialized
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except:
                pass


def text_to_speech(text: str, voice: str = "alloy", format: str = "m4a") -> Optional[tuple]:
    """
    Convert text to speech using OpenAI TTS
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        format: Output format - "m4a" (uses AAC) or "mp3"
        
    Returns:
        tuple: (audio_data: bytes, mime_type: str, filename: str) or None if failed
    """
    try:
        logger.info(f"Converting text to speech: {text[:50]}...")
        
        # OpenAI TTS supports: mp3, opus, aac, flac
        # For m4a, we use AAC format (m4a is AAC in MP4 container)
        if format.lower() == "m4a":
            response_format = "aac"
            mime_type = "audio/m4a"
            filename = "voice_reply.m4a"
        else:
            response_format = "mp3"
            mime_type = "audio/mpeg"
            filename = "voice_reply.mp3"
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format=response_format
        )
        
        audio_data = response.content
        logger.info(f"[OK] Generated speech audio ({len(audio_data)} bytes, format: {format})")
        
        return (audio_data, mime_type, filename)
        
    except Exception as e:
        logger.error(f"Error converting text to speech: {e}", exc_info=True)
        return None


def download_audio_from_url(url: str, mime_type: str = 'audio/m4a', api_key: str = None) -> Optional[str]:
    """
    Download audio file from URL and return base64-encoded data
    
    Args:
        url: URL to download audio from
        mime_type: MIME type of the audio file
        api_key: Optional API key for authentication
        
    Returns:
        str: Base64-encoded audio data, or None if failed
    """
    try:
        logger.info(f"[DOWNLOAD] Downloading audio from URL: {url}")
        
        # Prepare headers with API key if provided
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        audio_bytes = response.content
        base64_data = base64.b64encode(audio_bytes).decode('utf-8')
        logger.info(f"[OK] Downloaded {len(audio_bytes)} bytes, encoded to base64")
        return base64_data
    except Exception as e:
        logger.error(f"[ERROR] Error downloading audio from URL: {e}", exc_info=True)
        return None


def process_voice_message(attachments: list) -> Optional[str]:
    """
    Process voice message attachments and return transcribed text
    
    Args:
        attachments: List of attachment dicts
    
    Returns:
        str: Transcribed text from first audio attachment, or None
    """
    if not attachments:
        logger.warning("[WARN]  No attachments provided to process_voice_message")
        return None
    
    logger.info(f"[AUDIO] Processing {len(attachments)} attachment(s) for transcription...")
    
    # Find first audio attachment
    for i, attachment in enumerate(attachments):
        logger.debug(f"[AUDIO] Checking attachment #{i+1}: {attachment.get('filename', 'unknown')}")
        
        if is_audio_attachment(attachment):
            logger.info(f"[AUDIO] Found audio attachment: {attachment.get('filename')}")
            base64_data = attachment.get('data_base64')
            mime_type = attachment.get('mime_type', 'audio/m4a')
            
            # If no base64 data, try to get from URL
            if not base64_data:
                # Check for URL fields
                attachment_url = attachment.get('url') or attachment.get('download_url') or attachment.get('file_url') or attachment.get('attachment_url')
                if attachment_url:
                    logger.info(f"[AUDIO] No base64 data, trying to download from URL: {attachment_url}")
                    # Use Series API key for authentication
                    base64_data = download_audio_from_url(attachment_url, mime_type, api_key=SERIES_API_KEY)
            
            if base64_data:
                logger.info(f"[AUDIO] Attempting transcription with mime_type: {mime_type}, data length: {len(base64_data)}")
                result = transcribe_audio(base64_data, mime_type)
                if result:
                    logger.info(f"[AUDIO] [OK] Transcription successful: {result[:50]}...")
                else:
                    logger.warning(f"[AUDIO] [ERROR] Transcription returned None")
                return result
            else:
                logger.warning(f"[AUDIO] [WARN]  Audio attachment has no data_base64 or downloadable URL")
        else:
            logger.debug(f"[AUDIO] Attachment #{i+1} is not audio (mime: {attachment.get('mime_type', 'unknown')})")
    
    logger.warning("[WARN]  No audio attachments found or no base64 data available")
    return None

