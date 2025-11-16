"""
In-memory storage backend for tests.

This storage backend keeps all files in memory during tests to avoid writing to the file system.
This prevents pollution of the media directory with test data.
"""

from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from io import BytesIO


class InMemoryStorage(Storage):
    """
    A storage backend that stores files in memory.
    
    This is used for testing to avoid writing files to the file system.
    All files are stored in a class-level dictionary that persists across
    test instances but is cleared between test runs.
    """
    
    # Class-level storage to persist between instances
    _files = {}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def _save(self, name, content):
        """
        Save file content to memory.
        
        Args:
            name: The name/path of the file
            content: The file content (File object)
            
        Returns:
            The name of the saved file
        """
        # Read content into memory
        if hasattr(content, 'read'):
            file_content = content.read()
        else:
            file_content = content
        
        # Store in memory
        self._files[name] = BytesIO(file_content)
        return name
    
    def _open(self, name, mode='rb'):
        """
        Open a file from memory.
        
        Args:
            name: The name/path of the file
            mode: The file mode (ignored, always binary)
            
        Returns:
            ContentFile with the file content
        """
        if name not in self._files:
            raise FileNotFoundError(f"File {name} not found in memory storage")
        
        # Reset position to start
        self._files[name].seek(0)
        # Return a copy to avoid position conflicts
        content = self._files[name].getvalue()
        return ContentFile(content, name=name)
    
    def exists(self, name):
        """
        Check if a file exists in memory.
        
        Args:
            name: The name/path of the file
            
        Returns:
            True if the file exists, False otherwise
        """
        return name in self._files
    
    def delete(self, name):
        """
        Delete a file from memory.
        
        Args:
            name: The name/path of the file
        """
        if name in self._files:
            del self._files[name]
    
    def listdir(self, path):
        """
        List files in a directory.
        
        Args:
            path: The directory path
            
        Returns:
            Tuple of (directories, files)
        """
        # For simplicity, return empty lists
        # Can be enhanced if needed for specific tests
        return ([], [])
    
    def size(self, name):
        """
        Get the size of a file.
        
        Args:
            name: The name/path of the file
            
        Returns:
            The size of the file in bytes
        """
        if name not in self._files:
            raise FileNotFoundError(f"File {name} not found in memory storage")
        
        current_pos = self._files[name].tell()
        self._files[name].seek(0, 2)  # Seek to end
        size = self._files[name].tell()
        self._files[name].seek(current_pos)  # Restore position
        return size
    
    def path(self, name):
        """
        Get the path for a file.
        
        In tests, we don't have real paths, so we return the name.
        This allows code that accesses .path to still work during tests.
        
        Args:
            name: The name/path of the file
            
        Returns:
            The file name (since there's no real path)
        """
        return name
    
    def url(self, name):
        """
        Get the URL for a file.
        
        Args:
            name: The name/path of the file
            
        Returns:
            A fake URL for the file
        """
        # Return a fake URL that looks realistic for tests
        from django.conf import settings
        media_domain = getattr(settings, 'MEDIA_DOMAIN', 'http://localhost:8000')
        return f"{media_domain}/media/{name}"
    
    def get_available_name(self, name, max_length=None):
        """
        Get an available name for a file.
        
        If the file already exists, this method will return the same name
        (for tests, we don't care about overwriting).
        
        Args:
            name: The desired name/path
            max_length: Maximum length of the name
            
        Returns:
            The available name
        """
        return name
    
    @classmethod
    def clear(cls):
        """
        Clear all files from memory.
        
        This should be called between test runs to ensure a clean state.
        """
        cls._files.clear()

