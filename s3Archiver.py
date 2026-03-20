# s3Archive.py
import os
import sys
import struct
from Framer import Framer, Deframer # Add this line
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
            framer = Framer(archive)
            
            # Write magic header
            archive.write(b'SARCH') 
            
            for root, dirs, files in os.walk(source_dir):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    relative_path = os.path.relpath(filepath, source_dir)
                    
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    
                    compressed_content, huffman_codes, padding = self.compressor.compress(content)
                    codes_bytes = str(huffman_codes).encode('utf-8')
                    
                    # USE FRAMER FOR EVERYTHING
                    framer.frame(relative_path)           # 1. Filename
                    framer.frame(struct.pack('Q', len(content))) # 2. Original size
                    framer.frame(codes_bytes)             # 3. Huffman codes
                    framer.frame(struct.pack('B', padding))      # 4. Padding
                    framer.frame(compressed_content)      # 5. Compressed data
    
    def extract(self, dest_dir):
        """Extract and decompress files from archive to dest_dir."""
        os.makedirs(dest_dir, exist_ok=True)
        
        with open(self.archive_name, 'rb') as archive:
            deframer = Deframer(archive)
            
            # Verify magic header
            magic = archive.read(5)
            if magic != b'SARCH':
                raise ValueError("Invalid archive format")
            
            while True:
                # 1. Get filename
                filename_bytes = deframer.deframe()
                if filename_bytes is None: break # End of file
                filename = filename_bytes.decode('utf-8')

                # 2. Get original size
                size_bytes = deframer.deframe()
                original_size = struct.unpack('Q', size_bytes)[0]
                
                # 3. Get Huffman codes
                codes_bytes = deframer.deframe()
                huffman_codes = eval(codes_bytes.decode('utf-8'))
                
                # 4. Get padding
                padding_bytes = deframer.deframe()
                padding = struct.unpack('B', padding_bytes)[0]
                
                # 5. Get compressed content
                compressed_content = deframer.deframe()
                
                # Decompress and write
                content = self.compressor.decompress(compressed_content, huffman_codes, padding)
                output_path = os.path.join(dest_dir, filename)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                print(f"Extracted: {filename}")

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
