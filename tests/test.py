#!/usr/bin/env python3

import itertools
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
  ('foo', b'content foo\n'),
  ('bar', b'content bar\n'),
  ('baz', b'content baz\n'),
)

long = '%s/long.a' % root
long_content = (
  ('veryverylongfilename', b'veryverylong\n'),
  ('shortfilename', b'short\n'),
  ('evenveryverylongerfilename', b'evenveryverylonger\n'),
)

simple_merged = '%s/simple_merged.a' % root
simple_merged_content = (
  ('quux', b'content quux\n'),
)

long_merged = '%s/long_merged.a' % root
long_merged_content = (
  ('veryverylongmergedfilename', b'veryverylongmerged\n'),
)

class TestCase(unittest.TestCase):

  def check_content(self, archive, content):
    with TemporaryDirectory() as dest:
      archive.extract(dest)
      content = dict(content)
      for path in os.listdir(dest):
        self.assertTrue(path in content)
        with open('%s/%s' % (dest, path), 'rb') as f:
          self.assertEqual(f.read(), content[path])
        del content[path]
      self.assertEqual(len(content), 0)

class List(TestCase):

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

class Extract(TestCase):

  def perform(self, path, content):
    with ArchiveCopy(path) as archive:
      self.check_content(archive, content)

  def test_simple(self):
    return self.perform(simple, simple_content)

  def test_long(self):
    return self.perform(long, long_content)

class Merge(TestCase):

  def perform(self, archive, archive_content, merged, merged_content):
    with TemporaryDirectory() as dest:
      copy = '%s/%s' % (dest, os.path.basename(archive))
      shutil.copyfile(archive, copy)
      merged_copy = '%s/%s' % (dest, os.path.basename(merged))
      shutil.copyfile(merged, merged_copy)
      with ar.Archive(merged_copy) as m, ar.Archive(copy) as s:
        s.merge(m)
      content = dict(itertools.chain(archive_content,
                                     merged_content))
      with ar.Archive(copy) as archive:
        self.check_content(archive, content)

  def test_simple_simple(self):
    return self.perform(simple, simple_content,
                        simple_merged, simple_merged_content)

  def test_long_simple(self):
    return self.perform(long, long_content,
                        simple_merged, simple_merged_content)

  def test_simple_long(self):
    return self.perform(simple, simple_content,
                        long_merged, long_merged_content)

  def test_long_long(self):
    return self.perform(long, long_content,
                        long_merged, long_merged_content)

if __name__ == '__main__':
    unittest.main()
