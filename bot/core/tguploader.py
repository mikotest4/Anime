from time import time, sleep
from traceback import format_exc
from math import floor
from os import path as ospath
from aiofiles.os import remove as aioremove
from pyrogram.errors import FloodWait
import os
import asyncio
from asyncio.subprocess import PIPE

from bot import bot, Var
from .func_utils import editMessage, sendMessage, convertBytes, convertTime
from .reporter import rep

class TgUploader:
    def __init__(self, message):
        self.cancelled = False
        self.message = message
        self.__name = ""
        self.__qual = ""
        self.__client = bot
        self.__start = time()
        self.__updater = time()

    async def upload(self, path, qual):
        self.__name = ospath.basename(path)
        self.__qual = qual
        
        # Generate or get thumbnail for the video
        thumb_path = await self._get_or_generate_thumbnail(path)
        
        try:
            if Var.AS_DOC:
                return await self.__client.send_document(
                    chat_id=Var.FILE_STORE,
                    document=path,
                    thumb=thumb_path,
                    caption=f"<i>{self.__name}</i>",
                    force_document=True,
                    progress=self.progress_status
                )
            else:
                return await self.__client.send_video(
                    chat_id=Var.FILE_STORE,
                    video=path,
                    thumb=thumb_path,
                    caption=f"<i>{self.__name}</i>",
                    progress=self.progress_status
                )
        except FloodWait as e:
            await rep.report(f"FloodWait: Sleeping for {e.value} seconds", "warning")
            sleep(e.value * 1.5)
            return await self.upload(path, qual)
        except Exception as e:
            await rep.report(f"Upload Error: {str(e)}\n{format_exc()}", "error")
            raise e
        finally:
            # Clean up the uploaded file and generated thumbnail
            try:
                await aioremove(path)
                # Clean up generated thumbnail if it's not the default one
                if thumb_path and thumb_path.startswith("thumbs/"):
                    try:
                        os.remove(thumb_path)
                    except:
                        pass
            except Exception as cleanup_error:
                await rep.report(f"Cleanup Error: {str(cleanup_error)}", "warning")

    async def _get_or_generate_thumbnail(self, video_path):
        """Get existing thumbnail or generate one from the video"""
        
        # First, try to get existing valid thumbnail
        existing_thumb = await self._get_existing_thumbnail()
        if existing_thumb:
            return existing_thumb
        
        # Generate thumbnail from video
        generated_thumb = await self._generate_thumbnail_from_video(video_path)
        if generated_thumb:
            return generated_thumb
        
        # Try to download default thumbnail as fallback
        default_thumb = await self._download_default_thumbnail()
        if default_thumb:
            return default_thumb
        
        await rep.report("No thumbnail available, uploading without thumbnail", "warning")
        return None

    async def _get_existing_thumbnail(self):
        """Check for existing valid thumbnail files"""
        thumb_candidates = ["thumb.jpg", "thumb.png", "thumbnail.jpg", "thumbnail.png"]
        
        for thumb_file in thumb_candidates:
            if ospath.exists(thumb_file):
                try:
                    file_size = ospath.getsize(thumb_file)
                    if file_size > 0:
                        await rep.report(f"Using existing thumbnail: {thumb_file} ({file_size} bytes)", "info")
                        return thumb_file
                    else:
                        # Remove corrupted thumbnail
                        try:
                            os.remove(thumb_file)
                        except:
                            pass
                except Exception as e:
                    await rep.report(f"Error checking thumbnail {thumb_file}: {str(e)}", "warning")
        
        return None

    async def _generate_thumbnail_from_video(self, video_path):
        """Generate thumbnail from video file using FFmpeg"""
        try:
            # Create thumbs directory if it doesn't exist
            thumbs_dir = "thumbs"
            if not ospath.exists(thumbs_dir):
                os.makedirs(thumbs_dir)
            
            # Generate unique thumbnail filename
            video_name = ospath.splitext(ospath.basename(video_path))[0]
            thumb_filename = f"{video_name}_thumb.jpg"
            thumb_path = ospath.join(thumbs_dir, thumb_filename)
            
            await rep.report(f"Generating thumbnail for: {video_path}", "info")
            
            # FFmpeg command to generate thumbnail at 10% of video duration
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', '00:01:00',  # Start at 1 minute
                '-vframes', '1',    # Extract 1 frame
                '-vf', 'scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2',
                '-y',               # Overwrite output file
                thumb_path
            ]
            
            # Execute FFmpeg command
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=PIPE,
                stderr=PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and ospath.exists(thumb_path) and ospath.getsize(thumb_path) > 0:
                await rep.report(f"Thumbnail generated successfully: {thumb_path}", "info")
                return thumb_path
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                await rep.report(f"FFmpeg thumbnail generation failed: {error_msg}", "warning")
                
                # Try alternative method with different timestamp
                return await self._generate_thumbnail_alternative(video_path)
                
        except Exception as e:
            await rep.report(f"Error generating thumbnail: {str(e)}", "error")
            return None

    async def _generate_thumbnail_alternative(self, video_path):
        """Alternative thumbnail generation method"""
        try:
            # Create thumbs directory if it doesn't exist
            thumbs_dir = "thumbs"
            if not ospath.exists(thumbs_dir):
                os.makedirs(thumbs_dir)
            
            video_name = ospath.splitext(ospath.basename(video_path))[0]
            thumb_filename = f"{video_name}_thumb_alt.jpg"
            thumb_path = ospath.join(thumbs_dir, thumb_filename)
            
            # Try with 5% of video duration
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', '30',        # Start at 30 seconds
                '-vframes', '1',
                '-vf', 'scale=320:240',
                '-q:v', '2',        # High quality
                '-y',
                thumb_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=PIPE,
                stderr=PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and ospath.exists(thumb_path) and ospath.getsize(thumb_path) > 0:
                await rep.report(f"Alternative thumbnail generated: {thumb_path}", "info")
                return thumb_path
            else:
                await rep.report("Alternative thumbnail generation also failed", "warning")
                return None
                
        except Exception as e:
            await rep.report(f"Error in alternative thumbnail generation: {str(e)}", "error")
            return None

    async def _download_default_thumbnail(self):
        """Download the default thumbnail from URL"""
        if not Var.THUMB:
            return None
            
        try:
            import aiohttp
            import aiofiles
            
            thumb_path = "thumb_default.jpg"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(Var.THUMB) as response:
                    if response.status == 200:
                        async with aiofiles.open(thumb_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        # Validate downloaded thumbnail
                        if ospath.exists(thumb_path) and ospath.getsize(thumb_path) > 0:
                            await rep.report("Default thumbnail downloaded successfully", "info")
                            return thumb_path
                        else:
                            await rep.report("Downloaded thumbnail is invalid", "warning")
                            return None
                    else:
                        await rep.report(f"Failed to download thumbnail: HTTP {response.status}", "warning")
                        return None
        except Exception as e:
            await rep.report(f"Error downloading default thumbnail: {str(e)}", "error")
            return None

    async def progress_status(self, current, total):
        if self.cancelled:
            self.__client.stop_transmission()
        
        now = time()
        diff = now - self.__start
        
        # Update progress every 7 seconds or when complete
        if (now - self.__updater) >= 7 or current == total:
            self.__updater = now
            percent = round(current / total * 100, 2) if total > 0 else 0
            speed = current / diff if diff > 0 else 0
            eta = round((total - current) / speed) if speed > 0 else 0
            bar = floor(percent/8)*"█" + (12 - floor(percent/8))*"▒"
            
            progress_str = f"""‣ <b>Anime Name :</b> <b><i>{self.__name}</i></b>

‣ <b>Status :</b> <i>Uploading</i>
    <code>[{bar}]</code> {percent}%
    
    ‣ <b>Size :</b> {convertBytes(current)} out of ~ {convertBytes(total)}
    ‣ <b>Speed :</b> {convertBytes(speed)}/s
    ‣ <b>Time Took :</b> {convertTime(diff)}
    ‣ <b>Time Left :</b> {convertTime(eta)}

‣ <b>File(s) Encoded:</b> <code>{Var.QUALS.index(self.__qual) + 1} / {len(Var.QUALS)}</code>"""
            
            try:
                await editMessage(self.message, progress_str)
            except Exception as e:
                # Don't let progress update errors stop the upload
                pass

    def cancel_upload(self):
        """Cancel the current upload"""
        self.cancelled = True
