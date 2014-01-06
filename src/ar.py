#!/usr/bin/env python3


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

def _read_int(source, size):
  res = _read(source, size)
  try:
    return int(res)
  except:
    raise Exception('invalid integer: %s' % res.encode())

class Archive:

  class Header:

    def __init__(self, archive, source):
      self.__archive = archive
      name = _read(source, 16)
      name = name.decode('ascii').strip()
      if name != '/' and name != '//':
        # Look for the name in the extended filenames (//)
        if name.startswith('/'):
          name = int(name[1:])
          with SaveFileSeek(source):
            source.seek(archive._Archive__filenames.offset + name)
            name = ''
            while True:
              char = _read(source, 1).decode('ascii')
              if char == '\n':
                break
              name += char
        if name.endswith('/'):
          name = name[:-1]
      self.__name =  name
      mtime = _read(source, 12)
      oid =   _read(source, 6)
      gid =   _read(source, 6)
      mode =  _read(source, 8)
      self.__size =  _read_int(source, 10)
      magic = _read(source, 2)
      self.__offset = source.tell()

    def extract(self, destination):
      source = self.__archive._Archive__source
      source.seek(self.offset)
      size = self.size

      with open('%s/%s' % (destination, self.name), 'wb') as dest:
        while size > 0:
          buffer = source.read(min(4096, size))
          dest.write(buffer)
          size -= len(buffer)

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

  def __init__(self, source):
    if isinstance(source, str):
      self.__source = open(source, 'rb')
      self.__owned = True
    else:
      self.__source = source
      self.__owned = False
    with SaveFileSeek(self.__source):
      self.__source.seek(0, 2)
      file_size = self.__source.tell()
    if self.__source.read(8) != b'!<arch>\n':
      raise Exception('wrong archive magic string')
    self.__headers = []
    while self.__source.tell() < file_size:
      header = Archive.Header(self, self.__source)
      if header.name == '/':
        self.__index = header
      elif header.name == '//':
        self.__filenames = header
      else:
        self.__headers.append(header)
      self.__source.seek(header.space, 1)

  def __enter__(self):
    self.__source.__enter__()
    return self

  def __exit__(self, type, value, traceback):
    if self.__owned:
      self.__source.__exit__(type, value, traceback)

  @property
  def headers(self):
    for h in self.__headers:
      yield h

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
