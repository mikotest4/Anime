from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove as aioremove, mkdir, listdir
import os
import glob

from aiohttp import ClientSession
from torrentp import TorrentDownloader
from bot import LOGS
from bot.core.func_utils import handle_logs

class TorDownloader:
    def __init__(self, path="."):
        self.__downdir = path
        self.__torpath = "torrents/"
    
    @handle_logs
    async def download(self, torrent, name=None):
        if torrent.startswith("magnet:"):
            # For magnet links, extract the name from the magnet or use provided name
            torp = TorrentDownloader(torrent, self.__downdir)
            await torp.start_download()
            
            # Get the actual downloaded file path
            downloaded_path = await self._find_downloaded_file(name)
            if downloaded_path:
                LOGS.info(f"Successfully downloaded: {downloaded_path}")
                return downloaded_path
            else:
                LOGS.error("Downloaded file not found after torrent completion")
                return None
                
        elif torfile := await self.get_torfile(torrent):
            torp = TorrentDownloader(torfile, self.__downdir)
            await torp.start_download()
            await aioremove(torfile)
            
            # Get the actual downloaded file path
            downloaded_path = await self._find_downloaded_file(name)
            if downloaded_path:
                LOGS.info(f"Successfully downloaded: {downloaded_path}")
                return downloaded_path
            else:
                # Try to get from torrent info if available
                try:
                    torrent_name = torp._torrent_info._info.name()
                    full_path = ospath.join(self.__downdir, torrent_name)
                    if ospath.exists(full_path):
                        return full_path
                except:
                    pass
                
                LOGS.error("Downloaded file not found after torrent completion")
                return None
        
        return None

    @handle_logs
    async def _find_downloaded_file(self, expected_name=None):
        """Find the downloaded file in the downloads directory"""
        try:
            if not await aiopath.exists(self.__downdir):
                LOGS.error(f"Download directory {self.__downdir} does not exist")
                return None
            
            # List all files in download directory
            files = await listdir(self.__downdir)
            
            if not files:
                LOGS.error("No files found in download directory")
                return None
            
            # Log all files for debugging
            LOGS.info(f"Files in download directory: {files}")
            
            # If we have an expected name, try to find a match
            if expected_name:
                # Clean the expected name for comparison
                expected_clean = self._clean_filename(expected_name)
                
                for file in files:
                    file_clean = self._clean_filename(file)
                    # Check if the file matches the expected name (partial match)
                    if expected_clean.lower() in file_clean.lower() or file_clean.lower() in expected_clean.lower():
                        full_path = ospath.join(self.__downdir, file)
                        if ospath.isfile(full_path):
                            return full_path
            
            # If no expected name or no match found, get the largest video file
            video_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm')
            video_files = []
            
            for file in files:
                full_path = ospath.join(self.__downdir, file)
                if ospath.isfile(full_path) and file.lower().endswith(video_extensions):
                    file_size = ospath.getsize(full_path)
                    video_files.append((full_path, file_size))
            
            if video_files:
                # Return the largest video file
                largest_file = max(video_files, key=lambda x: x[1])
                LOGS.info(f"Selected largest video file: {largest_file[0]} ({largest_file[1]} bytes)")
                return largest_file[0]
            
            # If no video files, check for any files
            for file in files:
                full_path = ospath.join(self.__downdir, file)
                if ospath.isfile(full_path):
                    LOGS.info(f"Selected file: {full_path}")
                    return full_path
            
            LOGS.error("No suitable files found in download directory")
            return None
            
        except Exception as e:
            LOGS.error(f"Error finding downloaded file: {str(e)}")
            return None

    def _clean_filename(self, filename):
        """Clean filename for comparison by removing common variations"""
        if not filename:
            return ""
        
        # Remove file extension
        name = ospath.splitext(filename)[0]
        
        # Replace common separators with spaces
        name = name.replace('.', ' ').replace('-', ' ').replace('_', ' ')
        
        # Remove extra spaces
        name = ' '.join(name.split())
        
        return name

    @handle_logs
    async def get_torfile(self, url):
        if not await aiopath.isdir(self.__torpath):
            await mkdir(self.__torpath)
        
        tor_name = url.split('/')[-1]
        if not tor_name.endswith('.torrent'):
            tor_name += '.torrent'
            
        des_dir = ospath.join(self.__torpath, tor_name)
        
        try:
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        async with aiopen(des_dir, 'wb') as file:
                            async for chunk in response.content.iter_any():
                                await file.write(chunk)
                        LOGS.info(f"Downloaded torrent file: {des_dir}")
                        return des_dir
                    else:
                        LOGS.error(f"Failed to download torrent file. Status: {response.status}")
                        return None
        except Exception as e:
            LOGS.error(f"Error downloading torrent file: {str(e)}")
            return None
