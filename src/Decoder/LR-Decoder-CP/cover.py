#/usr/bin/env python

import sys, math

import settings
from lattice import Lattice

class Cover(object):
    '''coverage vector (wrapper) now also includes "last", so that Cover is the only signature.
    N.B.: must be cover | set (returning cover), not set | cover (returning set)'''

    repos = {}

    @staticmethod
    def clear():
	Cover.repos = {}

    def copyfrom(self, other):
	self.cover_set = other.cover_set
	self.first_span = other.first_span
	self.len = other.len
	self.hashval = other.hashval
	self.future_cost = other.future_cost
	self._ranges = other._ranges
		
    def __init__(self, ss, first_span):
	if (tuple(ss), first_span) in Cover.repos:
	    self.copyfrom(Cover.repos[(tuple(ss), tuple(first_span))])

	else:
	    self._ranges = None
	    self.cover_set = ss
	    self.first_span = first_span
	    self.len = len(ss)
	    self.hashval = hash((tuple(ss), tuple(self.first_span)))
	    #uncov = self.uncovered_ranges()
	    #self.future_cost = Lattice.this.getFutureCost(uncov)
	    self.future_cost = None
	    Cover.repos[(tuple(ss), tuple(first_span))] = self

    def uncovered_ranges(self, straight=True):
	last_unc = 0
	unc = False
	res = []
	if not straight:
	    s = self.uncovered()
	else:
	    s = self.cover_set | set([Lattice.this.sent_len])
	for i in range(Lattice.this.sent_len+1):
	    if i in s:
		if unc:
		    res.append( (last_unc, i) )
		unc = False
	    else:
		if not unc:
		    last_unc = i
		unc = True
	return res
				
    def uncovered(self):
	## complement set
	return set(range(Lattice.this.sent_len + 2)) - self.cover_set
	
    def __hash__(self):
	return self.hashval

    def ranges(self):
	'''yielding feasible ranges (with dist), based on last position, cover, and max-distortion-limit'''
	## start range = [last - max + 1, last + max + 1]
	if self._ranges is None:
	    n = Lattice.this.sent_len
	    max_distort = settings.opts.dist_limit
	    res = []
	    if len(self) == n:
		### '''final </s>'''
		### N.B.: Koehn bug: not counting the final distortion
		res = [((n, n + 1), n - self.last)]
	    else:
		irange = range(max(0, self.last - max_distort), \
		               min(n, self.last + max_distort + 1))

		if self.first_uncov not in irange:
		    irange += [self.first_uncov]

		for i in irange:
		    ## make sure you can get back (not exact!)
		    maxright = self.first_uncov + max_distort if i > self.first_uncov else n

		    for j in xrange(i + 1, min(n, i + settings.opts.max_phr_len) + 1):
			if (j - 1) not in self.cover_set and j <= maxright:
			    res.append (((i, j), abs(i - self.last)))
			else:
			    break  # stop here, try next i
	    self._ranges = res
	return self._ranges

    def advance(self, new_spans):
	new_set = set(range(self.first_span[0],self.first_span[1]))
	for span in new_spans:
	    new_set-=set(range(span[0], span[1]))
	first_span = () if not len(new_spans) else new_spans[0]
	c = Cover(self.cover_set | new_set, first_span)
	return c
    
    def getFutureCost(self, uncov=None):
	if self.future_cost is None:
	    uncov = self.uncovered_ranges() if uncov is None else uncov
	    self.future_cost = Lattice.this.getFutureCost(uncov)
	return self.future_cost
    
    def __str__(self):
	s = "".join(["*" if i in self.cover_set else "_" for i in range(Lattice.this.sent_len)])
	return " ".join([s,str(self.first_span)])

    def __len__(self):
	return self.len

    def __eq__(self, other):
	return self.hashval == other.hashval

class Signature():
    
    __slots__ = "cover", "uncovered_spans", "tgt_elided", "hashval", "future_cost"
    
    def __init__(self, cover_obj, uncov_spans, tgt_elided=''):
	self.cover = cover_obj
	self.uncovered_spans = uncov_spans
	self.tgt_elided = tgt_elided
	self.hashval = hash((tuple(uncov_spans), tgt_elided))
	self.future_cost = self.cover.getFutureCost(uncov_spans)
	
    def __str__(self):
	return " , ".join([str(self.cover),self.getSpanStr(),self.tgt_elided])    
	
    def __hash__(self):
	return self.hashval
    
    def __eq__(self, other):
	return self.hashval == other.hashval
    
    def advance(self, cover, new_spans=[], tgt_elided=''):
	if len(new_spans) == 0 and len(self.uncovered_spans) > 1:
	    cover = Cover(cover.cover_set, self.uncovered_spans[1])
	return Signature(cover,new_spans+self.uncovered_spans[1:], tgt_elided)
    
    def getSpanStr(self):
	return ",".join([str(span) for span in self.uncovered_spans])

def defaultCover(sent_len):
    return Cover(set(), (0,sent_len))

def defaultSign(sent_len):
    return Signature(defaultCover(sent_len),[],"<s>")
