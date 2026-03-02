import os
import sys
import re
import struct
from collections import Counter
import heapq

class HuffmanCompressor:
    class Node:
        def __init__(self, char=None, freq=0, left=None, right=None):
            self.char = char
            self.freq = freq
            self.left = left
            self.right = right
        
        def __lt__(self, other):
            return self.freq < other.freq
    
    def __init__(self):
        self.codes = {}
        self.reverse_codes = {}
    
    def build_tree(self, data):
        """Build Huffman tree from frequency analysis."""
        if not data:
            return None
        
        frequencies = Counter(data)
        
        if len(frequencies) == 1:
            char = list(frequencies.keys())[0]
            self.codes = {char: '0'}
            self.reverse_codes = {'0': char}
            return
        
        heap = [self.Node(char=char, freq=freq) for char, freq in frequencies.items()]
        heapq.heapify(heap)
        
        while len(heap) > 1:
            left = heapq.heappop(heap)
            right = heapq.heappop(heap)
            parent = self.Node(freq=left.freq + right.freq, left=left, right=right)
            heapq.heappush(heap, parent)
        
        root = heap[0]
        self.codes = {}
        self._generate_codes(root, '')
        self.reverse_codes = {v: k for k, v in self.codes.items()}
    
    def _generate_codes(self, node, code):
        """Recursively generate Huffman codes."""
        if node is None:
            return
        
        if node.char is not None:
            self.codes[node.char] = code if code else '0'
            return
        
        self._generate_codes(node.left, code + '0')
        self._generate_codes(node.right, code + '1')
    
    def compress(self, data):
        """Compress data using Huffman coding."""
        if not data:
            return b'', {}, 0
        
        self.build_tree(data)
        
        bit_string = ''.join(self.codes[byte] for byte in data)
        
        padding = 8 - len(bit_string) % 8
        if padding != 8:
            bit_string += '0' * padding
        
        compressed = bytearray()
        for i in range(0, len(bit_string), 8):
            byte = int(bit_string[i:i+8], 2)
            compressed.append(byte)
        
        return bytes(compressed), self.codes, padding
    
    def decompress(self, data, codes, padding):
        """Decompress data using Huffman codes."""
        if not data:
            return b''
        
        self.reverse_codes = {v: k for k, v in codes.items()}
        
        bit_string = ''.join(format(byte, '08b') for byte in data)
        
        if padding != 8:
            bit_string = bit_string[:-padding]
        
        decompressed = bytearray()
        current_code = ''
        
        for bit in bit_string:
            current_code += bit
            if current_code in self.reverse_codes:
                decompressed.append(self.reverse_codes[current_code])
                current_code = ''
        
        return bytes(decompressed)


class Archiver:
    ARCHIVE_EXTENSION = '.s3a'
    
    def __init__(self, archive_name):
        if not archive_name.endswith(self.ARCHIVE_EXTENSION):
            archive_name += self.ARCHIVE_EXTENSION
        self.archive_name = archive_name
        self.compressor = HuffmanCompressor()
    
    def create(self, source_dir):
        """Bundle and compress files from source_dir into an archive."""
        with open(self.archive_name, 'wb') as archive:
            # Write magic header
            archive.write(b'SARCH')  # Simple Archive
            
            for root, dirs, files in os.walk(source_dir):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    relative_path = os.path.relpath(filepath, source_dir)
                    
                    # Read file content
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    
                    # Compress content
                    compressed_content, huffman_codes, padding = self.compressor.compress(content)
                    
                    # Serialize Huffman codes as a dictionary
                    codes_str = str(huffman_codes)
                    codes_bytes = codes_str.encode('utf-8')
                    
                    # Write metadata
                    filename_bytes = relative_path.encode('utf-8')
                    archive.write(struct.pack('I', len(filename_bytes)))
                    archive.write(filename_bytes)
                    
                    # Write original size (for verification)
                    archive.write(struct.pack('Q', len(content)))
                    
                    # Write compressed size
                    archive.write(struct.pack('Q', len(compressed_content)))
                    
                    # Write Huffman codes
                    archive.write(struct.pack('I', len(codes_bytes)))
                    archive.write(codes_bytes)
                    
                    # Write padding value
                    archive.write(struct.pack('B', padding))
                    
                    # Write compressed content
                    archive.write(compressed_content)
    
    def extract(self, dest_dir):
        """Extract and decompress files from archive to dest_dir."""
        os.makedirs(dest_dir, exist_ok=True)
        
        with open(self.archive_name, 'rb') as archive:
            # Verify magic header
            magic = archive.read(5)
            if magic != b'SARCH':
                raise ValueError("Invalid archive format")
            
            while True:
                # Read filename length
                filename_len_bytes = archive.read(4)
                if not filename_len_bytes:
                    break
                
                filename_len = struct.unpack('I', filename_len_bytes)[0]
                filename = archive.read(filename_len).decode('utf-8')
                
                # Read original size
                original_size_bytes = archive.read(8)
                original_size = struct.unpack('Q', original_size_bytes)[0]
                
                # Read compressed size
                compressed_size_bytes = archive.read(8)
                compressed_size = struct.unpack('Q', compressed_size_bytes)[0]
                
                # Read Huffman codes
                codes_len_bytes = archive.read(4)
                codes_len = struct.unpack('I', codes_len_bytes)[0]
                codes_bytes = archive.read(codes_len)
                codes_str = codes_bytes.decode('utf-8')
                huffman_codes = eval(codes_str)  # Convert string back to dict
                
                # Read padding
                padding_bytes = archive.read(1)
                padding = struct.unpack('B', padding_bytes)[0]
                
                # Read compressed content
                compressed_content = archive.read(compressed_size)
                
                # Decompress content
                content = self.compressor.decompress(compressed_content, huffman_codes, padding)
                
                # Write file
                output_path = os.path.join(dest_dir, filename)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                print(f"Extracted: {filename} ({original_size} → {compressed_size} bytes)")

# Usage
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python s3Archiver.py [create|extract] <archive_name> [source_dir (create)|dest_dir (extract)]")
        sys.exit(1)
    
    command = sys.argv[1]
    archive_name = sys.argv[2]
    
    archiver = Archiver(archive_name)
    
    if command == 'create' and len(sys.argv) > 3:
        archiver.create(sys.argv[3])
        print(f"Archive created: {archive_name}")
    elif command == 'extract' and len(sys.argv) > 3:
        archiver.extract(sys.argv[3])
        print(f"Archive extracted to: {sys.argv[3]}")
    else:
        print("Invalid arguments")
