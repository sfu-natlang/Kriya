## @author baskaran
## revision 1 Maryam Saihbani,    03 Jul 13
## revision 2 Maryam Saihbani,    01 Dec 13
## revision 3 Maryam Saihbani,    01 Jan 15

import heapq
from operator import attrgetter

from entry_CP import Entry    # used for debugging
from cover import *
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
from refPhrases import RefPhrases
import settings

class Lazy(object):
    '''Implements the lazy merging algorithm of Huang and Chiang (2005)'''

    sent_id = -1
    wvec_lm = None
    cell_type = None
    is_last_cell = None
    refsLst = []
    hypScoreDict = {}
    __slots__ = "cubeDict", "bsize", "coverageHeap", "coverageDict", "cbp_diversity", "cbp_heap_diversity"

    def __init__(self, sent_indx, c_span, final_cell):
        self.coverageHeap = []
        self.cubeDict = {}
        self.coverageDict = {}
        self.cbp_diversity = settings.opts.cbp_diversity
        self.cbp_heap_diversity = settings.opts.cbp_heap_diversity
        self.bsize = settings.opts.cbp + 10 if settings.opts.cbp > 0 else float('inf')

        # set class attributes
        Lazy.sent_id = sent_indx
        Lazy.wvec_lm = settings.feat.lm
        Lazy.is_last_cell = final_cell
        Lazy.refsLst = []
        Lazy.createTracker();        # creates the tracking dict

    def __del__(self):
        '''Clear the data-structures'''

        if self.cubeDict:
            for cube_obj in self.cubeDict.itervalues():
                cube_obj = ''        # clears the lists in the Cube class
            del self.cubeDict
            del self.coverageDict
        Lazy.clearTracker()         # clears the tracking dict
	Cover.clear()               # clears repository of coverage vector

    def setSourceInfo(self, cube_indx, src_rule, src_span, spanT, cube_depth_hier, candRefsLst=[]):
        cube_obj = self.__getObject(cube_indx)
        Cube.setSourceInfo(cube_obj, src_rule, src_span, spanT, cube_depth_hier)
        if settings.opts.force_decode: Lazy.refsLst = candRefsLst

    def add2Cube(self, cube_indx, ruleLst):
        cube_obj = self.__getObject(cube_indx)
        Cube.addTuple(cube_obj, ruleLst)

    def __getObject(self, cube_indx):
        if cube_indx in self.cubeDict:
            cube_obj = self.cubeDict[cube_indx]
        else:
            cube_obj = Cube(self.cbp_heap_diversity)
            self.cubeDict[cube_indx] = cube_obj
        return cube_obj

    def mergeProducts(self):
        '''Calculate the top-N derivations by lazily finding the sum of log probs (equivalent to product of probs)'''

        # Initializations
        heap_indx = 0
        cb_pop_count = 0
        mP_candLst = []

        for cube_indx, cube_obj in self.cubeDict.iteritems():
            mP_candTup = ()
            mP_candTup = Cube.getBestItem(cube_obj, cube_indx)
            heapq.heappush(mP_candLst, (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3]))
            heap_indx += 1
	    # Queue diversity: add more hypotheses from each cube to the heap
            if self.cbp_heap_diversity > 1:
                diversityItems = []
                diversityItems = Cube.getkItems4Diversity(cube_obj, cube_indx, self.cbp_heap_diversity-1, mP_candTup[0], True)
                for mP_candTup in diversityItems:
                    heapq.heappush(mP_candLst, (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3]))
                    heap_indx += 1

        candLst_size = heap_indx
        while candLst_size > 0:
            # get the best item from the heap
            (h_score, h_indx, mP_entry_obj, cube_indx, mP_r) = heapq.heappop(mP_candLst)
            candLst_size -= 1

            # push the best item into coverageHeap from which the N-best list will be extracted
            if mP_entry_obj is not None:
                # @type mP_entry_obj Entry
                entry_exists = Lazy.indexHypothesis(mP_entry_obj.sign, Entry.getHypScore(mP_entry_obj), h_indx)
                if (entry_exists is None or not settings.opts.use_unique_nbest):
                    if self.cbp_diversity > 0: self.recordDiversity(cube_indx)
                    heapq.heappush(self.coverageHeap, (h_score, h_indx, mP_entry_obj, cube_indx, mP_r))
                elif entry_exists == -1:
                    pass
                else:
                    curr_h_indx = self.getItemIndxInHeap(entry_exists)
                    if self.cbp_diversity > 0: self.recordDiversity(cube_indx, self.coverageHeap[curr_h_indx][3])
                    self.coverageHeap[curr_h_indx] = (h_score, entry_exists, mP_entry_obj, cube_indx, mP_r)

            if cb_pop_count >= self.bsize and (self.cbp_diversity == 0 or ( self.cbp_diversity > 0 and \
                cube_indx in self.coverageDict and self.coverageDict[cube_indx] >= self.cbp_diversity )):
                continue

            # get the neighbours for the best item from the corresponding cube
            cube_obj = self.cubeDict[cube_indx]
            # @type cube_obj Cube
            neighbours = Cube.xploreNeighbours(cube_obj, cube_indx, mP_r)

            # add the neighbouring entries to the heap
            for mP_candTup in neighbours:
                if mP_candTup[1] is not None:
                    entry_exists = Lazy.checkHypothesis(mP_candTup[1].sign)
                    if entry_exists is None:                        # New hypothesis, increment cbp
                        cb_pop_count += 1

                new_candTup = (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3])
                heapq.heappush(mP_candLst, new_candTup)
                candLst_size += 1
                heap_indx += 1

        # Explore new items for increasing diversity (if required)
        if self.cbp_diversity > 0:
            for c_ind in self.cubeDict:
                diversityItems = []
                cube_obj = self.cubeDict[c_ind]
                if not c_ind in self.coverageDict:
                    diversityItems = Cube.getkItems4Diversity(cube_obj, c_ind, self.cbp_diversity, -10000)
                elif self.coverageDict[c_ind] < self.cbp_diversity:
                    diversityItems = Cube.getkItems4Diversity(cube_obj, c_ind, self.cbp_diversity - self.coverageDict[c_ind], -10000)
                else: continue

                for mP_candTup in diversityItems:
                    new_candTup = (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3])
                    heapq.heappush(self.coverageHeap, new_candTup)
                    heap_indx += 1

        Nbest_size = 0
        NbestLst = []
        self.coverageDict = {}
        heapq.heapify(self.coverageHeap)
        while self.coverageHeap:
            (h_score, h_indx, mP_entry_obj, cube_indx, mP_r) = heapq.heappop( self.coverageHeap )
            if ( Nbest_size < self.bsize or (Nbest_size >= self.bsize and self.cbp_diversity > 0 and \
                (not cube_indx in self.coverageDict or self.coverageDict[cube_indx] < self.cbp_diversity)) ):
                NbestLst.append( mP_entry_obj )
                Nbest_size += 1

                if self.cbp_diversity > 0:
                    if cube_indx in self.coverageDict: self.coverageDict[cube_indx] += 1
                    else: self.coverageDict[cube_indx] = 1

        return NbestLst

    def recordDiversity(self, cube_indx, dscnt_cube_indx=-1):
        if self.coverageDict.has_key(cube_indx): self.coverageDict[cube_indx] += 1
        else: self.coverageDict[cube_indx] = 1

        if dscnt_cube_indx >= 0 and self.coverageDict.has_key(dscnt_cube_indx):
            self.coverageDict[dscnt_cube_indx] -= 1

    def getItemIndxInHeap(self, item_indx):
        curr_h_indx = 0
        for heapItem in self.coverageHeap:
            if heapItem[1] == item_indx:
                return curr_h_indx
            curr_h_indx += 1

    # classmethods for tracking unique hypotheses
    @classmethod
    def createTracker(cls):
        '''Creates the DoD used for tracking unique hypotheses'''

        cls.hypScoreDict = {}

    @classmethod
    def indexHypothesis(cls, hyp, curr_hyp_score, heap_indx):
        '''Index target hypotheses with their respective nbest-list index'''

        if cls.hypScoreDict.has_key(hyp):
            (existing_indx, best_hyp_score) = cls.hypScoreDict[hyp]
            if curr_hyp_score > best_hyp_score:
                cls.hypScoreDict[hyp] = (existing_indx, curr_hyp_score)
                return existing_indx
            else:
                return -1
        else:
            cls.hypScoreDict[hyp] = (heap_indx, curr_hyp_score)
            return None

    @classmethod
    def checkHypothesis(cls, hyp):
        '''Check if an existing hypothesis has the same target as the current one'''

        if cls.hypScoreDict.has_key(hyp):
            return cls.hypScoreDict[hyp][0]
        else:
            return None

    @classmethod
    def getHypothesisStatus(cls, hyp, curr_hyp_score):
        '''Get the status of hypothesis generated, to avoid multiple identical target in the n-best list'''

        # Only the best hypothesis for any target sequence needs to be stored, if use_unique_nbest is True
        # In the absence of accurate LM score, the score excluding the LM score is used to decide the best hyp
        # All the identical hypotheses will all have same LM score and so this approach is correct
        if cls.hypScoreDict.has_key(hyp):
            if cls.hypScoreDict[hyp][1] >= curr_hyp_score:
                return 0                                       # existing hyp is better or not different; return 0 to ignore this
            else:
                return -1                                      # curr hyp has better score; return -1
        else:
            return -2                                          # Current one is new hypothesis; return -2

    @classmethod
    def clearTracker(cls):
        '''Clears the DoD used for tracking unique hypotheses'''

        cls.hypScoreDict = {}
        del cls.hypScoreDict

    @classmethod
    def candMatchesRef(cls, hyp):
        '''Checks whether the candidate hypothesis matches at least one given reference'''

        if hyp.startswith("<s>"): hyp = hyp[4:]
        if hyp.endswith("</s>"): 
            hyp = hyp[:-5]
            return RefPhrases.isValidRefSent(cls.sent_id, hyp)
        #return RefPhrases.isValidRefPhrNSent(cls.sent_id, hyp)
        return RefPhrases.isValidRefPhrStart(cls.sent_id, hyp)


class Cube(object):
    __slots__ = "dimensions", "src_side", "src_span", "spanLst", "ruleLst", "initDimVec", "trackCubeDict", "depth_hier", "cbp_heap_diversity", "cover", "LMCache", "setCube", "boundLst"

    def __init__(self, cbp_heap_diversity, isSet=False):
        '''Initializes the Cube surface'''

        self.dimensions = 0
        self.src_side = ''
	self.src_span = ()
        self.spanLst = []
        self.ruleLst = []
        self.initDimVec = []
        self.trackCubeDict = {}                               # dictionay that tracks the filled boxes in the cube
        self.cbp_heap_diversity = cbp_heap_diversity
	self.cover = None
        self.LMCache = {}
        self.setCube = isSet
        self.boundLst = None

    def __del__(self):
        '''Clear the rule and feature lists'''

        self.dimensions = 0
        del self.spanLst[:]
        del self.ruleLst[:]
        del self.trackCubeDict
        del self.LMCache
        del self.boundLst

    def setSourceInfo(self, src_rule, src_span, spanLst, cube_depth_hier):
        '''Sets the source side rule, span and spans of nonterminals for the current cube'''

        self.src_side = src_rule
	self.src_span = src_span
        self.spanLst = spanLst[:]
        self.depth_hier = cube_depth_hier
	self.setCube = True if src_rule.endswith("X__2 X__3") else False

    def addTuple(self, rLst):
        '''Adds the rule and feature lists to the current cube'''

        self.dimensions += 1
        self.ruleLst[len(self.ruleLst):] = [ rLst[:] ]
	if self.dimensions == 1:
	    c = rLst[0].groupSign()
	    self.cover = c.advance(self.spanLst)
        elif self.setCube:
            self.boundLst = []
            prevTgt = None
            for indx,ent_obj in enumerate(self.ruleLst[-1]):
                if prevTgt!= ent_obj.tgt:
                    prevTgt = ent_obj.tgt
                    self.boundLst.append(indx)
				
    def getBestItem(self, cube_indx):
        '''Get the best item in the Cube and return its derivation'''

        entryLst = []
        indexVector = []
        self.initDimVec = [0] * self.dimensions
        bestItemsLst = []
	# create a tuple of (hyp,rule) and merge them
        for j in range( self.dimensions ):
            entryLst.append( self.ruleLst[j][0] )
            indexVector.append(0)
        (score, entry_obj) = self.mergeEntries(entryLst, cube_indx)
        self.trackCubeDict[ tuple(indexVector) ] = 1

        # negate the score before returning
        return ( -score, entry_obj, cube_indx, indexVector )

    def xploreNeighbours(self, cube_indx, r):
        '''Explore the neighbouring cells of the given index-vector'''

        neighbours = []
        if not self.trackCubeDict.has_key( tuple(r) ):
            print "Error: The indexVctor %s doesn't *exist* in self.trackCubeDict" % (tuple(r))
        elif self.trackCubeDict[tuple(r)] != 1 and self.cbp_heap_diversity > 1 :
            return neighbours
        elif self.trackCubeDict[tuple(r)] != 1:
            print "Error: The value of indexVctor %s in self.trackCubeDict is %d (should be 1 instead)" % (tuple(r), self.trackCubeDict[tuple(r)])
            return neighbours

        dimension = -1
        for curr_indx in r:
            dimension += 1
            next_indx = curr_indx + 1
            if len(self.ruleLst[dimension]) <= next_indx: continue
            r[dimension] = next_indx

            entryLst = self.initDimVec[:]
            dim = 0
            for der_indx in r:
                entryLst[dim] = self.ruleLst[dim][der_indx]
                dim += 1

            r1 = r[:]     # deep copy the vector 'r'
            if not self.trackCubeDict.has_key( tuple(r1) ):
                self.trackCubeDict[ tuple(r1) ] = 1

                (score, entry_obj) = self.mergeEntries(entryLst, cube_indx)
                # negate the score before appending it to neighbours list
                neighbours.append( (-score, entry_obj, cube_indx, r1) )
            r[dimension] = curr_indx

        # The set of new {r1} now form the open frontier, i.e. cells whose neighbours are yet to be explored
        # The cell r can be closed as its neighbours has been completely explored
        # The open and closed frontiers are indicated by values 1 and 0 respectively in the self.trackCubeDict
        if not self.trackCubeDict.has_key( tuple(r) ):
            print "Error: The indexVctor %s doesn't *exist* in self.trackCubeDict" % (tuple(r))
        elif self.trackCubeDict[tuple(r)] != 1:
            print "Error: The value of indexVctor %s in self.trackCubeDict is %d (should be 1 instead)" % (tuple(r), self.trackCubeDict[tuple(r)])
        self.trackCubeDict[ tuple(r) ] = 0

        return neighbours

    def getkItems4Diversity(self, cube_indx, k, bestScore, heap_div=False):
        '''Get k additional items for increasing the diversity in the Cube'''

        neighbours = []
        if self.setCube:
            indexVector = [0 for i in self.initDimVec]
            for bound in self.boundLst:
                indexVector[1] = bound
                r = tuple(indexVector)
                if not self.trackCubeDict.has_key( r ):
                    div_candTup = self.getItemForVect(cube_indx, indexVector)
                    if div_candTup[0] < bestScore: bestScore= div_candTup[0]
                    neighbours.append(div_candTup)
                if len(neighbours) >= min(k,5): break
        if len(neighbours) >= k: return neighbours
        uselessEntires = 0
        while True:
            new_items_so_far = len(neighbours)
            for r in self.trackCubeDict.keys():
                if self.trackCubeDict[r] == 0: continue         # ignore the closed frontiers

                for div_candTup in self.xploreNeighbours(cube_indx, list(r)):
                    if heap_div or (div_candTup[1] is not None):
                        neighbours.append(div_candTup)
                    if (div_candTup[1] is not None) and div_candTup[0] < bestScore: uselessEntires = 0
                    uselessEntires +=1

                # We have found 'k' new items for diversity; break and return them
                if len(neighbours) >= k: break
                if uselessEntires >= 5 : return neighbours

            # If all the entries in the Cube have been explored already Or if it didn't add any new items:
            #   break and return empty list
            if not neighbours or len(neighbours) == new_items_so_far or len(neighbours) >= k: break

        return neighbours

    def getItemForVect(self, cube_indx, r):
        '''Get the item corresponding to vector r in the Cube and return its derivation'''

        if self.trackCubeDict.has_key( tuple(r) ):
            return (0, None, cube_indx, r)
        entryLst = self.initDimVec[:]

        # Iterate thro' the tuples: compute log prob of first entry in every tuple and sum them
        dim = 0
        for der_indx in r:
            entryLst[dim] = self.ruleLst[dim][der_indx]
            dim += 1
        (score, entry_obj) = self.mergeEntries(entryLst, cube_indx)
        self.trackCubeDict[ tuple(r) ] = 1

        # negate the score before returning
        return ( -score, entry_obj, cube_indx, list(r) )

    def mergeEntries(self, entriesLst, cube_indx):

        dim = 0
        tmpSpanLst=[]
        for ent_obj in entriesLst:
            # @type ent_obj Entry
            if dim == 0:	## order is important, 0 : hypotheses list
                score = ent_obj.score
                fVec = ent_obj.featVec[:]
                cons_item = ConsequentItem(ent_obj.tgt, ent_obj.tgt_elided, ent_obj.lm_right)
            else:
                score += ent_obj.score
                for f_idx,feat_val in enumerate(ent_obj.featVec):
                    fVec[f_idx] += feat_val
		# Compute distortion value (glue and regular rules)
                try:
		    dist = ent_obj.dist.get([j-i for (i,j) in self.spanLst])
                except:
                    print self.spanLst, ent_obj.src, ent_obj.tgt
                    print str(ent_obj)
                    exit(1)
		if ent_obj.isGlue(): 
		    fVec[9] -= dist
		    score += (-dist)*settings.opts.weight_dg
		else: 
		    fVec[8] -= dist
		    score += (-dist)*settings.opts.weight_d
                # Add antecedent item to the consequent item
                cons_item.addAntecedent( ent_obj.tgt_elided, ent_obj.tgt_elided, ent_obj.lm_right )
            dim += 1

        cons_item.mergeAntecedents(Lazy.is_last_cell)
        #if ( Lazy.is_last_cell ):
        #    cons_item.addRightSMarker()

        if settings.opts.force_decode and not Lazy.candMatchesRef(cons_item.tgt):
            return (score, None)                             # Hypothesis wouldn't lead to reference; ignore this

        """
            Get hypothesis status from the classmethod (in Lazy); hypothesis status can take one of these three values:
            -2 : Hyp was not seen earlier; create a new entry
            -1 : Hyp was seen earlier but current one has a better score; create a new entry to replace the existing one
             0 : Hyp was seen earlier and has a poor score than the existing one; ignore this
        """       
	(score, lm_heu, lm_lprob, e_tgt, out_state) = self.helperLM(score, cons_item, fVec[6])
	fVec[6] += lm_lprob
	sign = entriesLst[0].sign.advance(self.cover, self.spanLst, e_tgt)
	hyp_status = Lazy.getHypothesisStatus(sign, score)

        """  Should we recombine hypothesis?
	     A new hypothesis is always added; query LM for lm-score and create new entry_obj.
	     If an identical hypothesis exists then the current hyp is added under below conditions:
	     i) the use_unique_nbest flag is False (add new hyp; but use the LM score of the existing one)
	     ii) use_unique_nbest is True and the new hyp is better than the existing one.
	"""	
 
	if hyp_status == 0 and settings.opts.use_unique_nbest:
	    entry_obj = None
	    score += sign.future_cost
	else:
            entry_obj = Entry(score, cons_item.tgt, fVec, e_tgt, sign, self.depth_hier, (), entriesLst[1], entriesLst[:], 0.0, out_state)
            score = entry_obj.score + entry_obj.getFutureScore()
        return (score, entry_obj)

    def helperLM(self, score, cons_item, preLMProb):
        '''Helper function for computing the two functions p() and q() and scoring'''

        lm_lprob = 0.0
        is_new_elided_tgt = True
        new_out_state = cons_item.r_lm_state
        dummy_lmProb = 0
        lm_heu = 0
        if settings.opts.no_lm_score:   
            dummy_len = min(cons_item.e_len, settings.opts.n_gram_size-1)
            e_tgt = " ".join(cons_item.eTgtLst[cons_item.e_len-dummy_len:])
            return (score, lm_heu, lm_lprob, e_tgt, new_out_state)

        # Computing n-gram LM-score for partial candidate hypotheses
        if cons_item.eTgtLst[0] == "<s>":
            dummy_len = min(cons_item.e_len, settings.opts.n_gram_size-1)
            dummy_tgtLst = cons_item.eTgtLst[:dummy_len]
            if settings.opts.use_srilm: lm_H = SRILangModel.getLMHeuCost(dummy_tgtLst, dummy_len)	## SRILM does not work now, becareful!!
            else: lm_H = KENLangModel.queryLMShort(dummy_tgtLst, dummy_len)
            lm_lprob = (lm_H - preLMProb)
            dummy_lmProb = lm_lprob
            e_tgt = cons_item.e_tgt
        
        if cons_item.e_len < settings.opts.n_gram_size:
            if cons_item.eTgtLst[0] != "<s>":
                sys.stderr.write("ERR: history is less than %d-gram, but it is not the start of sentence:\n%s\n%s" % (settings.opts.n_gram_size, cons_item.e_tgt, cons_item.tgt))
                exit(1)
            lm_lprob = 0
            # Compute the LM probabilities for all complete m-grams in the elided target string, and
            # Compute heuristic prob for first m-1 terms in target
        else:
            if settings.opts.use_srilm:
                (lm_lprob, e_tgt) = SRILangModel.scorePhrnElide(cons_item.eTgtLst, cons_item.e_len, cons_item.mgramSpans)
                #lm_H = SRILangModel.getLMHeuCost(cons_item.eTgtLst, cons_item.e_len)
            else:
                if cons_item.e_tgt in self.LMCache:
                    (lm_lprob, e_tgt, new_out_state) = self.LMCache[cons_item.e_tgt]
                else:
                    (lm_lprob, e_tgt, new_out_state) = KENLangModel.scorePhrnElideRight(cons_item.eTgtLst, cons_item.e_len, cons_item.mgramSpans, cons_item.statesLst, cons_item.r_lm_state)
                    self.LMCache[cons_item.e_tgt] = (lm_lprob, e_tgt, new_out_state)
                #lm_H = KENLangModel.getLMHeuCost(cons_item.e_tgt, cons_item.eTgtLst, cons_item.e_len)
            if e_tgt == cons_item.e_tgt: 
                sys.stderr.write("ERR: history has not been changed!!:\n%s\n%s" % (cons_item.e_tgt, cons_item.tgt))
                exit(1)
                is_new_elided_tgt = False

        #if ( Lazy.is_last_cell ):                           # lm_heu is added permanently in the last cell
        #    if is_new_elided_tgt: lm_lprob += lm_H
        #    lm_H = 0.0

        #lm_heu = Lazy.wvec_lm * lm_H
        lm_heu = 0
        #if is_new_elided_tgt:
        #    score += lm_heu + (Lazy.wvec_lm * lm_lprob)     # Pruning score including LM and heuristic
        lm_lprob += dummy_lmProb		# start of sentence prob
        score += (Lazy.wvec_lm * lm_lprob)     # Pruning score including LM

        return (score, lm_heu, lm_lprob, e_tgt, new_out_state)


class ConsequentItem(object):
    """ Class for an Consequent Item (result of merging two antecendents)"""

    __slots__ = "tgt", "e_tgt", "e_len", "eTgtLst", "anteItems", "edgeTup", "r_lm_state", "statesLst", "mgramSpans"

    def __init__(self, raw_tgt, raw_e_tgt, lm_right):
        self.tgt = raw_tgt
        self.e_tgt = raw_e_tgt
        self.eTgtLst = []
        self.anteItems = []
        self.r_lm_state = lm_right
        self.setState()

    def verify(self):
        ''' Verifies the state object by printing the state (for debugging) '''
        if self.r_lm_state is not None: KENLangModel.printState(self.r_lm_state)
        else: print "  >> Consequent state : None"
        if len(self.anteItems) >= 1:
            if self.anteItems[0][2] is not None: KENLangModel.printState(self.anteItems[0][2])
            else: print "    >>> Antecedent state-1 : None"
        if len(self.anteItems) == 2:
            if self.anteItems[1][2] is not None: KENLangModel.printState(self.anteItems[1][2])
            else: print "    >>> Antecedent state-2 : None"

    def setState(self):
        '''Set the beginning and end state of the consequent item as a tuple'''

        #beg_state = 0
        #end_state = 0
        #if self.tgt.startswith('X__1') or self.tgt.startswith('S__1'): beg_state = 1
        #elif self.tgt.startswith('X__2'): beg_state = 2

        #if self.tgt.endswith('X__1'): end_state = 1
        #elif self.tgt.endswith('X__2'): end_state = 2
	
	## It is always fixed for LR-Hiero
        beg_state = 0
        end_state = 1

        self.edgeTup = (beg_state, end_state)

    def __del__(self):
        '''Clear the data-structures'''

        del self.eTgtLst
        del self.anteItems
        del self.statesLst
        del self.mgramSpans
        self.r_lm_state = None

    def addAntecedent(self, tgt, e_tgt, right_lm):
        self.anteItems.append( (tgt, e_tgt, right_lm) )

    def addLeftSMarker(self):
        '''Add the left sentence marker and also adjust offsets to reflect this'''

        if (self.edgeTup[0] == 0 and not self.tgt.startswith('<s>')) \
            or (self.edgeTup[0] == 1 and not self.anteItems[0][0].startswith('<s>')) \
            or (self.edgeTup[0] == 2 and not self.anteItems[1][0].startswith('<s>')):
                #self.tgt = '<s> ' + self.tgt
                self.e_tgt = '<s> ' + self.e_tgt

    def addRightSMarker(self):
        '''Add the right sentence marker'''

        if (self.edgeTup[1] == 0 and not self.tgt.endswith('</s>')) \
            or (self.edgeTup[1] == 1 and not self.anteItems[0][0].endswith('</s>')) \
            or (self.edgeTup[1] == 2 and not self.anteItems[1][0].endswith('</s>')):
                #self.tgt = self.tgt + ' </s>'
                self.e_tgt = self.e_tgt + ' </s>'
                self.r_lm_state = None
                if self.edgeTup[1] != 0: self.edgeTup = (self.edgeTup[0], 0)

    def mergeAntecedents(self, is_last_cell):

        if not is_last_cell:	self.setLMState()
        self.e_len = 0
        self.statesLst = []
        self.mgramSpans = []
        mgram_beg = 0
        tgtItems = []
        curr_state = None
	
        tgtItems = [self.tgt]
        self.eTgtLst = self.e_tgt.split()
        self.e_len = len(self.eTgtLst)
        tgtItems.append( self.anteItems[0][0] )
        tempLst = self.anteItems[0][1].split()
        next_state = self.anteItems[0][2]

        if is_last_cell:
            tgtItems.append("</s>")
            tempLst.append("</s>")
            if next_state is not None:
                print "lm_state is not none!!!"
                print tgtItems
                print tempLst

        for ante_term in tempLst:
                if ante_term == settings.opts.elider:
                    if (self.e_len - mgram_beg >= settings.opts.n_gram_size \
                            or curr_state is not None) and mgram_beg != self.e_len:
                        self.mgramSpans.append( (mgram_beg, self.e_len) )
                        self.statesLst.append( curr_state )
                    curr_state = next_state
                    if settings.opts.no_lm_state: mgram_beg = self.e_len + 1
                    else: mgram_beg = self.e_len + settings.opts.n_gram_size
                self.eTgtLst.append(ante_term)
                self.e_len += 1

        if (self.e_len - mgram_beg >= settings.opts.n_gram_size \
                or curr_state is not None) and mgram_beg != self.e_len:
            self.mgramSpans.append( (mgram_beg, self.e_len) )
            self.statesLst.append( curr_state )

        self.tgt = ' '.join(tgtItems)
        self.e_tgt = ' '.join(self.eTgtLst)

    def setLMState(self):
        '''Set the right LM state for the consequent item'''

        if self.r_lm_state is not None: pass
        elif self.edgeTup[1] == 1:
            self.r_lm_state = self.anteItems[0][2]
        elif self.edgeTup[1] == 2:
            self.r_lm_state = self.anteItems[1][2]
