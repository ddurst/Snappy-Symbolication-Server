import os
import cPickle as pickle
from symLogging import LogDebug, LogMessage, LogError
from symUtil import mkdir_p

class Cache(object):
  def Update(self, oldMRU, newMRU, symbols):
    maxSize = self.MAX_SIZE
    oldMruSet = set(oldMRU[:maxSize])
    newMruSet = set(newMRU[:maxSize])

    inserted = newMruSet.difference(oldMruSet)
    evicted = oldMruSet.difference(newMruSet)

    LogDebug(
      "Evicting {} and inserting {} entries in {}".format(
      len(evicted),
      len(inserted),
      self.__class__))

    self.Evict(evicted)
    self.Insert(inserted, symbols)

class MemoryCache(Cache):
  def __init__(self, options):
    self.sCache = {}
    self.MAX_SIZE = options["maxMemCacheFiles"]

  def Evict(self, libs):
    for key in libs:
      self.sCache.pop(key)

  def Insert(self, libs, symbols):
    for lib in libs:
      self.sCache[lib] = symbols[lib]

  def Get(self, lib):
    return self.sCache.get(lib)

  def LoadCacheEntries(self, MRU, diskCache):
    LogMessage("Initializing memory cache from disk cache")
    for lib in MRU[:self.MAX_SIZE]:
      LogDebug("Loading library " + str(lib))
      cachedLib = diskCache.Get(lib)
      if cachedLib:
	self.sCache[lib] = diskCache.Get(lib)
      else:
        # this is safe, iterating over a "copy" of the MRU because of slice operator
        MRU.remove(lib)
    LogMessage("Finished initializing memory cache from disk cache")

class DiskCache(Cache):
  def __init__(self, options):
    self.diskCachePath = options["diskCachePath"]
    self.MAX_SIZE = options["maxDiskCacheFiles"]
    mkdir_p(self.diskCachePath)

  def Evict(self, libs):
    for libName, breakpadId in libs:
      path = self.MakePath(libName, breakpadId)
      # Remove from the disk
      LogDebug("Evicting {} from disk cache.".format(path))
      try:
        os.remove(path)
      except OSError:
        pass

  def Insert(self, libs, symbols):
    for lib in libs:
      self.Store(symbols[lib], lib[0], lib[1])

  def Get(self, lib):
    path = self.MakePath(lib[0], lib[1])
    symbolInfo = None

    try:
      with open(path, 'rb') as f:
        symbolInfo = pickle.load(f)
    except (IOError, EOFError, pickle.PickleError) as ex:
      LogError("Could not load pickled lib {}: {}".format(path, ex))
      try:
        os.remove(path)
        LogMessage("Removed unreadable pickled lib {}".format(path))
      except Exception as ex2:
        LogError("Could not remove unreadable pickled file {}: {}".format(path, ex2))
    except Exception as ex:
      LogError("Unexpected error loading pickled lib[{}]: {}".format(path, ex))

    return symbolInfo

  # Walk through the cache directory collecting files.
  def GetCacheEntries(self):
    fileList = []

    # The symbolFiles are located at
    # {diskCachePath}/{breakpadId}@{libName}
    for root, _, filenames in os.walk(self.diskCachePath):
      for filename in filenames:
        filePath = os.path.relpath(
                    os.path.normpath(
                      os.path.join(root, filename)), self.diskCachePath)

        # Get the libName and breakpadId components of the path
        breakpadId, libName = filePath.split("@")

        fileList.append((libName, breakpadId))

    return fileList

  def Store(self, symbolInfo, libName, breakpadId):
    path = self.MakePath(libName, breakpadId)
    with open(path, 'wb') as f:
      pickle.dump(symbolInfo, f, pickle.HIGHEST_PROTOCOL)

  def MakePath(self, libName, breakpadId):
    return os.path.join(
            self.diskCachePath,
            "@".join((breakpadId, libName)))

