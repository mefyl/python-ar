#!/usr/bin/env python3

import os.path
import shutil
import sys

from tempfile import TemporaryDirectory

root = os.path.dirname(__file__)
sys.path.append('%s/../src' % root)

import ar
import unittest

class ArchiveCopy(ar.Archive):

  def __init__(self, path):
    self.__dir = TemporaryDirectory()
    dest = '%s/%s' % (self.__dir.name, os.path.basename(path))
    shutil.copyfile(path, dest)
    super().__init__(dest)

  def __enter__(self):
    self.__dir.__enter__()
    return super().__enter__()

  def __exit__(self, type, value, traceback):
    super().__exit__(type, value, traceback)
    self.__dir.__exit__(type, value, traceback)

simple = '%s/simple.a' % root
simple_content = (
  ('foo', b'content foo'),
  ('bar', b'content bar'),
  ('baz', b'content baz'),
)

long = '%s/long.a' % root
long_content = (
  ('veryverylongfilename', b'veryvery'),
  ('shortfilename', b'short'),
  ('evenveryverylongerfilename', b'evenveryverylonger'),
)

class List(unittest.TestCase):

  def perform(self, path, content):
    with ArchiveCopy(path) as archive:
      names = set(name for name, content in content)
      for header in archive.headers:
        self.assertTrue(header.name in names)
        names.remove(header.name)
    self.assertEqual(len(names), 0)

  def test_simple(self):
    return self.perform(simple, simple_content)

  def test_long(self):
    return self.perform(long, long_content)

class Extract(unittest.TestCase):

  def perform(self, path, content):
    with ArchiveCopy(path) as archive, TemporaryDirectory() as dest:
      files = dict(content)
      archive.extract(dest)
      for path in os.listdir(dest):
        self.assertTrue(path in files)
        del files[path]
      self.assertEqual(len(files), 0)

  def test_simple(self):
    return self.perform(simple, simple_content)

  def test_long(self):
    return self.perform(long, long_content)

if __name__ == '__main__':
    unittest.main()
