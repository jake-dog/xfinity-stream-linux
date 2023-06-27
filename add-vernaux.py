"""
MIT License

Copyright (c) 2023 David Buchanan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This is widevine_fixup.py version 0.1. Find the latest version here:
https://gist.github.com/DavidBuchanan314/c6b97add51b97e4c3ee95dc890f9e3c8
"""

import sys

if len(sys.argv) != 3:
	print(f"Usage: {sys.argv[0]} input.so output.so")
	exit()

import ctypes

class Elf64_Ehdr(ctypes.Structure):
	_fields_ = [
		('e_ident', ctypes.c_ubyte * 16),
		('e_type', ctypes.c_uint16),
		('e_machine', ctypes.c_uint16),
		('e_version', ctypes.c_uint32),
		('e_entry', ctypes.c_uint64),
		('e_phoff', ctypes.c_uint64),
		('e_shoff', ctypes.c_uint64),
		('e_flags', ctypes.c_uint32),
		('e_ehsize', ctypes.c_uint16),
		('e_phentsize', ctypes.c_uint16),
		('e_phnum', ctypes.c_uint16),
		('e_shentsize', ctypes.c_uint16),
		('e_shnum', ctypes.c_uint16),
		('e_shstrndx', ctypes.c_uint16),
	]

# Incomplete list, for matching on sh_type
class SHT:
    SHT_SYMTAB = 2
    SHT_STRTAB = 3
    SHT_RELA = 4
    SHT_HASH = 5
    SHT_DYNAMIC = 6
    SHT_NOTE = 7
    SHT_NOBITS = 8
    SHT_REL = 9
    SHT_SHLIB = 10
    SHT_DYNSYM = 11
    SHT_GNU_verdef = 0x6ffffffd
    SHT_GNU_verneed = 0x6ffffffe
    SHT_GNU_versym = 0x6fffffff

class Elf64_Shdr(ctypes.Structure):
	_fields_ = [
		('sh_name', ctypes.c_uint32),
		('sh_type', ctypes.c_uint32),
		('sh_flags', ctypes.c_uint64),
		('sh_addr', ctypes.c_uint64),
		('sh_offset', ctypes.c_uint64),
		('sh_size', ctypes.c_uint64),
		('sh_link', ctypes.c_uint32),
		('sh_info', ctypes.c_uint32),
		('sh_addralign', ctypes.c_uint64),
		('sh_entsize', ctypes.c_uint64),
	]

class Elf64_Verneed(ctypes.Structure):
    _fields_ = [
        ('vn_version', ctypes.c_uint16),
        ('vn_cnt', ctypes.c_uint16),
        ('vn_file', ctypes.c_uint32),
        ('vn_aux', ctypes.c_uint32),
        ('vn_next', ctypes.c_uint32),
    ]

class Elf64_Vernaux(ctypes.Structure):
    _fields_ = [
        ('vna_hash', ctypes.c_uint32),
        ('vna_flags', ctypes.c_uint16),
        ('vna_other', ctypes.c_uint16),
        ('vna_name', ctypes.c_uint32),
        ('vna_next', ctypes.c_uint32),
    ]

with open(sys.argv[1], "rb") as infile:
	elf = bytearray(infile.read())

ehdr = Elf64_Ehdr.from_buffer(elf)

shdrs = [
	Elf64_Shdr.from_buffer(memoryview(elf)[ehdr.e_shoff + i * ehdr.e_shentsize:])
	for i in range(ehdr.e_shnum)
]

strtab = shdrs[ehdr.e_shstrndx]

def resolve_string(elf, strtab, stridx, count=False):
	if count:
		str_start = strtab.sh_offset
		for _ in range(stridx):
			str_start = elf.index(b"\0", str_start) + 1
	else:
		str_start = strtab.sh_offset + stridx
	str_end = elf.index(b"\0", str_start)
	return bytes(elf[str_start:str_end])

shdr_by_name = {
	resolve_string(elf, strtab, shdr.sh_name): shdr
	for shdr in shdrs
}

gnuversionr = shdr_by_name[b".gnu.version_r"]
assert gnuversionr.sh_type == SHT.SHT_GNU_verneed
#print("GNU version r offset=", gnuversionr.sh_offset, "info=", gnuversionr.sh_info, "size=",gnuversionr.sh_size)

# Strings used in the ".gnu.version_r" section are stored here
dynstr = shdr_by_name[b".dynstr"]

# Code ported from binutils/readelf.c
idx = 0
for cnt in range(0,gnuversionr.sh_info):
    verneed = Elf64_Verneed.from_buffer(memoryview(elf)[gnuversionr.sh_offset+idx:])
    filename = resolve_string(elf, dynstr, verneed.vn_file) 
    #print("Verneed cnt=",cnt,"next address=",verneed.vn_next,"count=",verneed.vn_cnt,"aux=",verneed.vn_aux,"filename=",filename.decode('utf-8'))
    if b"libc.so.6" == resolve_string(elf, dynstr, verneed.vn_file):
        aidx = idx + verneed.vn_aux
        has_dt_relr = False
        for vn_cnt in range(0,verneed.vn_cnt):
            vernaux = Elf64_Vernaux.from_buffer(memoryview(elf)[gnuversionr.sh_offset+aidx:])
            name = resolve_string(elf, dynstr, vernaux.vna_name)
            #print("Vernaux cnt=",vn_cnt,"next=", vernaux.vna_next,"name=", name.decode('utf-8'),"hash=", vernaux.vna_hash, "version=", vernaux.vna_other, "flags=", vernaux.vna_flags)
            if name == b"GLIBC_ABI_DT_RELR":
                print("library already has GLIBC_ABI_DT_RELR")
                has_dt_relr = True
                break
            if not vernaux.vna_next:
                vernaux.vna_next=368-aidx
                break
            aidx += vernaux.vna_next

        # Add "GLIBC_ABI_DT_RELR" if its not already there
        if not has_dt_relr:
            print("adding GLIBC_ABI_DT_RELR to library")
            vernaux = Elf64_Vernaux.from_buffer(memoryview(elf)[gnuversionr.sh_offset+368:])
            vernaux.vna_name = 2004
            vernaux.vna_hash = 0xfd0e42
            vernaux.vna_other = 20
            vernaux.vna_flags = 0
            vernaux.vna_next = 0
            verneed.vn_cnt += 1

        break
    idx += verneed.vn_next

with open(sys.argv[2], "wb") as outfile:
	outfile.write(memoryview(elf))
