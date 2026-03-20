# Framer.py
import struct

class Framer:
    def __init__(self, file_des):
        # Constructor for the framer
        self.file_des = file_des
    #@staticmethod
    def frame(self, data):
        # Adds a frame header w/data length
        if isinstance(data, str):
            data = data.encode()
        length = len(data)
        header = struct.pack('!I', length)
        framed_data = header + data
        self.file_des.write(framed_data)
        return framed_data
    
class Deframer:
    def __init__(self, file_des):
        self.file_des = file_des

    def deframe(self, buffer_size=4096, decode=False):
        try:
            # 1. Read the 4-byte header
            header = self._read_exactly(4)
            if not header: 
                return None # Normal EOF
            
            length = struct.unpack('!I', header)[0]
            
            # 2. Handle 0-length "keep-alive" or "EOF" markers
            if length == 0:
                return "" if decode else b""

            # 3. Read exactly 'length' bytes
            data = self._read_exactly(length)
            if data is None:
                raise EOFError("Connection closed before full frame received")
            
            return data.decode() if decode else data

        except Exception as e:
            print(f"Deframing error: {e}")
            return None

    def _read_exactly(self, n):
        """Helper to ensure we get exactly n bytes."""
        result = b''
        while len(result) < n:
            chunk = self.file_des.read(n - len(result))
            if not chunk: # Socket closed
                return None if not result else result # Return what we have or None
            result += chunk
        return result
         
