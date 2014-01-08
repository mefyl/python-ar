#!/usr/bin/env python3

import shutil

from tempfile import TemporaryDirectory

class SaveFileSeek:

  def __init__(self, f):
    self.__file = f

  def __enter__(self):
    self.__position = self.__file.tell()

  def __exit__(self, type, value, traceback):
    self.__file.seek(self.__position)

def _read(source, size):
  res = source.read(size)
  if len(res) != size:
    raise Exception('truncated file')
  return res

def _read_int(source, size, base = 10):
  res = _read(source, size)
  if res == b' ' * size:
    # Special files (/ and //) have blank fields
    return 0
  try:
    return int(res, base)
  except:
    raise Exception('invalid integer: %s' % res)

class Archive:

  magic_string = b'!<arch>\n'
  magic_number = b'\x60\x0A'

  class File:

    def __init__(self, header):
      self.__header = header
      self.__source = header._Header__archive._Archive__source
      self.__source.seek(header.offset)
      self.__read = 0

    def __enter__(self):
      return self

    def __exit__(self, type, value, backtrace):
      pass

    def read(self, size):
      left = self.__header.size - self.__read
      if left == 0:
        return b''
      res = self.__source.read(min(size, left))
      self.__read += len(res)
      return res

  class Header:

    def __init__(self, archive, source):
      self.__archive = archive
      self.__position = source.tell()
      name = _read(source, 16)
      name = name.decode('ascii').strip()
      if name != '/' and name != '//':
        # Look for the name in the extended filenames (//)
        if name.startswith('/'):
          name = int(name[1:])
          filenames = archive._Archive__filenames
          if name >= filenames.size:
            raise Exception('out of bound extended name: %s' % name)
          with SaveFileSeek(source):
            source.seek(filenames.offset + name)
            name = ''
            while True:
              char = _read(source, 1).decode('ascii')
              if char == '\n':
                break
              name += char
        if name.endswith('/'):
          name = name[:-1]
      self.__name = name
      self.__mtime = _read_int(source, 12)
      self.__oid = _read_int(source, 6)
      self.__gid = _read_int(source, 6)
      self.__mode = _read_int(source, 8, 8)
      self.__size =  _read_int(source, 10)
      if _read(source, 2) != Archive.magic_number:
        raise Exception('wrong magic number for header %s' % name)
      self.__offset = source.tell()

    def extract(self, destination):
      with self.open() as src, open('%s/%s' % (destination, self.name), 'wb') as dst:
        shutil.copyfileobj(src, dst)

    @property
    def name(self):
      return self.__name

    @property
    def size(self):
      return self.__size

    @property
    def space(self):
      return self.__size + self.__size % 2

    @property
    def offset(self):
      return self.__offset

    @property
    def mtime(self):
      return self.__mtime

    @property
    def oid(self):
      return self.__oid

    @property
    def gid(self):
      return self.__gid

    @property
    def mode(self):
      return self.__mode

    @property
    def position(self):
      return self.__position

    def open(self):
      return Archive.File(self)

  def __init__(self, path):
    self.__path = path
    self.__source = open(path, 'rb')
    with SaveFileSeek(self.__source):
      self.__source.seek(0, 2)
      file_size = self.__source.tell()
    if self.__source.read(8) != Archive.magic_string:
      raise Exception('wrong archive magic string')
    self.__headers = []
    self.__index = None
    self.__filenames = None
    while self.__source.tell() < file_size:
      header = Archive.Header(self, self.__source)
      if header.name == '/':
        self.__index = header
      elif header.name == '//':
        self.__filenames = header
      else:
        self.__headers.append(header)
      self.__source.seek(header.space, 1)
    self.__inserted = []

  def __enter__(self):
    self.__source.__enter__()
    return self

  def __exit__(self, type, value, traceback):
    if self.__inserted:
      with TemporaryDirectory() as tmp:
        tmp_path = '%s/archive.a' % tmp
        with open(tmp_path, 'wb') as dst:
          dst.write(Archive.magic_string)
          if self.__filenames is not None:
            filenames_offset = self.__filenames.size
          else:
            filenames_offset = 0
          filenames = []
          extended = []
          for header in self.__inserted:
            name = header.name + '/'
            if len(name) > 16:
              filenames.append(name)
              newname = ('/%s' % filenames_offset)
              filenames_offset += len(name) + 1
              name = newname
            extended.append((name, header))
          header_start_size = 16 + 12 + 6 + 6 + 8 # Up to the file size
          header_size = header_start_size + 10 + 2
          if filenames_offset % 2 == 0:
            filenames_space = filenames_offset
            filenames_pad = False
          else:
            filenames_space = filenames_offset + 1
            filenames_pad = True
          if self.__filenames is None:
            if filenames:
              # Create extended filenames
              empty = b'//' + b' ' * (header_start_size - 2)
              dst.write(empty)
              dst.write(('%10d' % filenames_space).encode('ascii'))
              dst.write(Archive.magic_number)
              for filename in filenames:
                dst.write(filename.encode('ascii') + b'\n')
              if filenames_pad:
                dst.write(b'\n')
            else:
              # No need for extended filenames
              pass
          else:
            self.__source.seek(self.__filenames.position)
            if filenames:
              # Append extended filenames
              dst.write(self.__source.read(header_start_size))
              dst.write(('%10d' % filenames_space).encode('ascii'))
              dst.write(Archive.magic_number)
              self.__source.seek(self.__filenames.offset)
              dst.write(self.__source.read(self.__filenames.size))
              for filename in filenames:
                dst.write(filename.encode('ascii') + b'\n')
              if filenames_pad:
                dst.write(b'\n')
            else:
              # Just copy the extended filenames
              dst.write(self.__source.read(
                header_size + self.__filenames.space))
          # Copy old files
          self.__source.seek(next(self.headers).position)
          shutil.copyfileobj(self.__source, dst)
          # Append new files
          for name, header in extended:
            dst.write(name.encode('ascii'))
            dst.write(b' ' * (16 - len(name)))
            stats = '%12d%6d%6d%8o%10d' % (header.mtime,
                                           header.oid, header.gid,
                                           header.mode, header.size)
            dst.write(stats.encode('ascii'))
            dst.write(b'\x60\x0A')
            shutil.copyfileobj(header.open(), dst)
        self.__source.__exit__(type, value, traceback)
        shutil.copyfile(tmp_path, self.__path)
    else:
      self.__source.__exit__(type, value, traceback)

  @property
  def headers(self):
    for h in self.__headers:
      yield h

  def extract(self, destination):
    for header in self.headers:
      header.extract(destination)

  def merge(self, archive):
    for header in archive.headers:
      self.__inserted.append(header)


if __name__ == '__main__':
  import optparse
  usage = "usage: %prog mode [options] file"
  parser = optparse.OptionParser(usage = usage)
  modes = optparse.OptionGroup(parser, 'Modes')
  parser.add_option_group(modes)
  modes.add_option('-l', '--list',
                   action = 'store_true',
                   help = 'list the content of the archive',
                   default = False)
  modes.add_option('-x', '--extract',
                   action = 'store_true',
                   help = 'extract the content of the archive',
                   default = False)
  parser.add_option('-d', '--destination',
                    action = 'store',
                    type = 'string',
                    help = 'where to extract the archive',
                    default = '.')
  (options, args) = parser.parse_args()
  modes_count = sum(map(int, (options.list, options.extract)))
  if modes_count == 0:
    raise Exception('missing mode')
  elif modes_count > 1:
    raise Exception('duplicate mode')
  if len(args) != 1:
    raise Exception('missing file')
  path = args[0]
  with Archive(path) as archive:
    if options.list:
      for header in archive.headers:
        print(header.name)
    elif options.extract:
      import distutils.dir_util
      distutils.dir_util.mkpath(options.destination)
      for header in archive.headers:
        header.extract(options.destination)
