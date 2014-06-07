# This file was created automatically by SWIG 1.3.29.
# Don't modify this file, modify the SWIG interface instead.
# This file is compatible with both classic and new-style classes.

import _srilm
import new
new_instancemethod = new.instancemethod
def _swig_setattr_nondynamic(self,class_type,name,value,static=1):
    if (name == "thisown"): return self.this.own(value)
    if (name == "this"):
        if type(value).__name__ == 'PySwigObject':
            self.__dict__[name] = value
            return
    method = class_type.__swig_setmethods__.get(name,None)
    if method: return method(self,value)
    if (not static) or hasattr(self,name):
        self.__dict__[name] = value
    else:
        raise AttributeError("You cannot add attributes to %s" % self)

def _swig_setattr(self,class_type,name,value):
    return _swig_setattr_nondynamic(self,class_type,name,value,0)

def _swig_getattr(self,class_type,name):
    if (name == "thisown"): return self.this.own()
    method = class_type.__swig_getmethods__.get(name,None)
    if method: return method(self)
    raise AttributeError,name

def _swig_repr(self):
    try: strthis = "proxy of " + self.this.__repr__()
    except: strthis = ""
    return "<%s.%s; %s >" % (self.__class__.__module__, self.__class__.__name__, strthis,)

import types
try:
    _object = types.ObjectType
    _newclass = 1
except AttributeError:
    class _object : pass
    _newclass = 0
del types


initLM = _srilm.initLM
deleteLM = _srilm.deleteLM
getIndexForWord = _srilm.getIndexForWord
getWordForIndex = _srilm.getWordForIndex
readLM = _srilm.readLM
getWordProb = _srilm.getWordProb
getUnigramProb = _srilm.getUnigramProb
getBigramProb = _srilm.getBigramProb
getTrigramProb = _srilm.getTrigramProb
getSentenceProb = _srilm.getSentenceProb
corpusStats = _srilm.corpusStats
getCorpusProb = _srilm.getCorpusProb
getCorpusPpl = _srilm.getCorpusPpl
howManyNgrams = _srilm.howManyNgrams


