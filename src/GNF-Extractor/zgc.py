# implements the algorithm for computing a normalized hierarchical
# analysis of a given alignment between a pair of sentences / phrases
# that is described in 'Extracting Synchronous Grammar Rules from
# Word-level Alignments in Linear Time' by H. Zhang, D. Gildea and
# D. Chiang. Currently it implements the n^2 shift-reduce algorithm.

from __future__ import division
import sys
import time
from collections import defaultdict

class zgc:

    __slots__ = "m", "n", "ldict", "udict", "alignfor", "alignback", "f_prefix", "e_prefix", "r_chain", "tree_nodes", "verbose", "zgc_style", "max_phr_len"

    def __init__(self, max_phrlen=5):
        self.max_phr_len = max_phrlen

    def getAlignTree(self, elen, flen, alignTupLst):
        alignTupLst = self.getUnalignedIndices(elen, alignTupLst, 0)
        alignTupLst = self.getUnalignedIndices(flen, alignTupLst, 1)

        self.initDS()
        self.n = elen
        self.m = flen
        for (i,j) in alignTupLst:
            if i == -1 or j == -1: continue
            self.alignfor[i].append(j)
            self.alignback[j].append(i)
        if self.verbose:
            print "n:",self.n,"m:",self.m,"align:",alignTupLst
            print "alignfor:",self.alignfor
            print "alignback:",self.alignback

        self.fprefixScore()
        self.eprefixScore()
        self.getPhrasalTree()
        if self.verbose:
            self.printPhrase()

        del alignTupLst
        # self.tree_nodes is the normalized hierarchical analysis of a given alignment
        # the tree is a list of nodes arranged as an in-order traversal of the tree
        return self.tree_nodes

    def getUnalignedIndices(self, p_len, alignTupLst, tup_indx):
        wordAlignSet = set([])
        for aTup in alignTupLst:
            if aTup[tup_indx] not in wordAlignSet:
                wordAlignSet.add( aTup[tup_indx] )

        for i in xrange(p_len):
            if i not in wordAlignSet:
                if tup_indx == 0: alignTupLst.append( (i, -1) )
                else: alignTupLst.append( (-1, i) )

        return alignTupLst

    def initDS(self):
        self.m = -1
        self.n = -1
        self.ldict = {}
        self.udict = {}
        self.alignfor = defaultdict(list)
        self.alignback = defaultdict(list)
        self.f_prefix = {}
        self.e_prefix = {}
        self.r_chain = []
        self.tree_nodes = []
        self.nodesSet = set([])
        self.verbose = False
        self.zgc_style = False

    def fprefixScore(self):
        j_sum = 0
        for j in xrange(-1, self.m):
            if j in self.alignback:
                j_sum += len(self.alignback[j])
            self.f_prefix[j] = j_sum
        if self.verbose:
            print "f_prefix:",
            for jj in self.f_prefix: print "%d:%d" % (jj,self.f_prefix[jj]),
            print

    def eprefixScore(self):
        i_sum = 0
        for i in xrange(-1, self.n):
            if i in self.alignfor: 
                i_sum += len(self.alignfor[i])
            self.e_prefix[i] = i_sum
        if self.verbose:
            print "e_prefix:",
            for ii in self.e_prefix: print "%d:%d" % (ii,self.e_prefix[ii]),
            print

    def compute_l_and_u(self,x,y):
        if x == y: 
            (_,lval,uval) = self.l_u(x,y)
            self.ldict[x,y] = lval
            self.udict[x,y] = uval
        else:
            (_,l,u) = self.l_u(x,y)
            self.ldict[x,y] = l
            self.udict[x,y] = u

            # If there are unaligned words (min pos = -1) then attach them *only* in the top.
            # Attaching them in other places will result in 'loose' rules having
            # unaligned words in the boundary.
            if self.ldict[x,y] == -1 and x == 0 and y == self.n-1:
                self.ldict[x,y] = 0
        if self.verbose:
            print "x:",x,"y:",y,"l(x,y):",self.ldict[x,y],"u(x,y):",self.udict[x,y]

    def getPhrasalTree(self):
        X = []
        X.append(0)
        # base case
        self.compute_l_and_u(0,0)
        if self.f(0,0) == 0:
            if self.isSpanLegal(0, 0, self.ldict[0,0], self.udict[0,0]):
                self.tree_nodes.append( ((0,0),(self.ldict[0,0],self.udict[0,0])) )
        # recursive case
        for y in xrange(1,self.n):
            X.append(y)
            for x in reversed(X):
                # Ignore if the span is larger than max phrase length
                if (y - x) >= self.max_phr_len:
                    self.r_chain = []
                    for i in xrange(x+1,y+1):
                        if i in X:
                            X.remove(i)
                        if self.alignfor.has_key(i): self.r_chain.append(i)
                    self.getRightTreeNodes()
                    continue

                # produces values for ldict[x,y] and udict[x,y]
                self.compute_l_and_u(x,y)
                #if self.ldict[x,y] == -1 and self.udict[x,y] >= 0:
                #    self.ldict[x,y] = self.udict[x,y]

                # If an unaligned word is found on the source side,
                # generate the nodes of successive right children of left chaining tree so far.
                # This corresponds to the nodes in the right chaining tree. In the end continue ...
                if self.ldict[x,y] == -1 or self.udict[x,y] == -1:
                    self.getRightTreeNodes()
                    self.r_chain = []
                    continue

                if (x == 0 and y == self.n-1) or self.f(x,y) == 0:
                    if not (x == 0 and y == self.n-1):
                        if self.isSpanLegal(x, y, self.ldict[x,y], self.udict[x,y]):
                            self.tree_nodes.append( ((x,y),(self.ldict[x,y],self.udict[x,y])) )
                        if len(self.r_chain) == 0 or y != self.r_chain[len(self.r_chain)-1]:
                            if self.alignfor.has_key(y): self.r_chain.append(y)

                    #if self.f(x,y) != 0: continue
                    self.r_chain = []
                    # adding this creates the ValueError problem in compute_l_and_u
                    for i in xrange(x+1,y+1):
                        if i in X:
                            X.remove(i)
                        if self.alignfor.has_key(i): self.r_chain.append(i)
                    self.getRightTreeNodes()

        # get the remaining right nodes
        self.getRightTreeNodes()

    def isSpanLegal(self, x, y, l, u):
        ## For the span to be legal: 
        ##  1) the source-side length should not be greater than max_phr_len
        ##  2) the source and target phrases can not be fully covered by the respective spans
        ##  3) the edges are tight (no unaligned words on the edges)
        #if (y - x) < self.max_phr_len and (y + 1 - x) < self.n and (u + 1 - l) < self.m and ((x,y),(l,u)) not in self.nodesSet and \
        if (y - x) < self.max_phr_len and ((x,y),(l,u)) not in self.nodesSet and \
                self.alignfor.has_key(x) and self.alignfor.has_key(y) and self.alignback.has_key(l) and self.alignback.has_key(u):
                #self.alignfor[x][0] != -1 and self.alignfor[y][0] != -1 and self.alignback[l][0] != -1 and self.alignback[u][0] != -1:
            self.nodesSet.add( ((x,y),(l,u)) )
            return True
        return False

    def getRightTreeNodes(self):
        """ emit nodes from the right children of a left branching tree
        """

        # Nothing to do if there is just one node in the chain
        if len(self.r_chain) < 2:
            self.r_chain = []
            return

        for indx, xx in enumerate( self.r_chain ):
            for yy in self.r_chain[indx+1:]:
                self.compute_l_and_u(xx,yy)
                # f(x,y) ensures non-crossing alignments within a span
                if self.f(xx,yy) == 0:
                    if self.isSpanLegal(xx, yy, self.ldict[xx,yy], self.udict[xx,yy]):
                        self.tree_nodes.append( ((xx,yy),(self.ldict[xx,yy],self.udict[xx,yy])) )

        self.r_chain = []
        return

    def printPhrase(self):

        for (e, f) in self.tree_nodes:
            if self.zgc_style:
                print "ZGC notation: ((%d,%d), (%d,%d))" % (e[0]+1,e[1]+1,f[0]+1,f[1]+1)
            else:
                print "((%d,%d), (%d,%d))" % (e[0],e[1],f[0],f[1])

        return None

    # this does the expensive computation of l(x,y) and u(x,y)
    # use the constant time functions u() and l() instead
    # the only exception is when you want to find l(x,x) and u(x,x)
    # to start off the recursive u() and l() functions
    def l_u(self,x,y):
        l_list = []
        for i in xrange(x,y+1):
            if i in self.alignfor:
                l_list.extend(self.alignfor[i])
        (lmin, umax) = (min(l_list), max(l_list)) if len(l_list) > 0 else (-1,-1)
        if x not in self.alignfor or y not in self.alignfor: lmin = -1
        return (l_list, lmin, umax)

    # l(x,y) = min{ l(x, x), l(x+1, y) }
    # and lp1 = l(x+1, y)
    def l(self,x,lp1):
        l_list = self.alignfor[x] + [lp1] if lp1 != -1 else self.alignfor[x]                      # Original line
        return min(l_list) if x in self.alignfor else lp1      # Original line

    # u(x,y) = max{ u(x, x), u(x+1, y) }
    # and up1 = u(x+1, y)
    def u(self,x,up1):
        u_list = self.alignfor[x] + [up1]
        return max(u_list) if x in self.alignfor else up1

    # f(x,y) = f_prefix(u(x,y)) - f_prefix(l(x,y) - 1) - (e_prefix(y) - e_prefix(x-1))
    def f(self,x,y):
        if y not in self.e_prefix:
            raise ValueError("y not found in e_prefix", y)

        return self.f_prefix[self.udict[x,y]] \
                - self.f_prefix[max(self.ldict[x,y] - 1, -1)] \
                - (self.e_prefix[y] \
                - self.e_prefix[x-1])

if __name__ == '__main__':
    max_phrlen = 10
    align_tree = zgc(max_phrlen)
    fin = open(sys.argv[1], "r")
    for line in fin:
        # align_tree is the normalized hierarchical analysis of a given alignment
        # the tree is a list of nodes arranged as an in-order traversal of the tree
        line = line.strip()
        aTupLst = []
        t_beg = time.time()
        (e_str, f_str, cnt, falign, ralign) = line.split(' ||| ')
        print falign
        for align in falign.split(' ## '):
            del aTupLst[:]
            for align_pair in align.split():
                (e, f) = align_pair.split('-')
                e = -1 if e == 'Z' else int(e)
                f = -1 if f == 'Z' else int(f)
                aTupLst.append((e, f))
            print aTupLst
            alignSpanLst = align_tree.getAlignTree(len(e_str.split()), len(f_str.split()), aTupLst)
            for align_span in alignSpanLst: print align_span
        print "Time taken : %g sec" % (time.time() - t_beg)
