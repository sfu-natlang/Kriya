## @author baskaran
## 16 Aug 09

import heapq
from operator import attrgetter

from featureManager import FeatureManager as fm
from languageModelManager import LanguageModelManager as lmm
from features import StatefulFeatures as sff
from hypothesis import Hypothesis    # used for debugging
from refPhrases import RefPhrases
import settings

class Lazy(object):
    '''Implements the lazy merging algorithm of Huang and Chiang (2005)'''

    sent_id = -1
    cell_span = None
    cell_type = None
    is_last_cell = None
    refsLst = []
    hypScoreDict = {}
    __slots__ = "cubeDict", "bsize", "coverageHeap", "coverageDict", "cbp_diversity"

    def __init__(self, sent_indx, c_span, c_type, final_cell):
        self.coverageHeap = []
        self.cubeDict = {}
        self.coverageDict = {}
        self.cbp_diversity = settings.opts.cbp_diversity
        self.bsize = settings.opts.cbp + 10 if settings.opts.cbp > 0 else float('inf')

        # set class attributes
        Lazy.sent_id = sent_indx
        Lazy.cell_span = c_span
        Lazy.cell_type = c_type
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
        Lazy.clearTracker();         # clears the tracking dict

    def setSourceInfo(self, cube_indx, src_rule, spanT, cube_depth_hier, candRefsLst=[]):
        cube_obj = self.__getObject(cube_indx)
        Cube.setSourceSide(cube_obj, src_rule, spanT, cube_depth_hier)
        if settings.opts.force_decode: Lazy.refsLst = candRefsLst

    def add2Cube(self, cube_indx, ruleLst):
        cube_obj = self.__getObject(cube_indx)
        Cube.addTuple(cube_obj, ruleLst)

    def __getObject(self, cube_indx):
        if self.cubeDict.has_key(cube_indx):
            cube_obj = self.cubeDict[cube_indx]
        else:
            #cube_obj = Cube(self.cell_span, self.cell_type, self.is_last_cell)
            cube_obj = Cube()
            self.cubeDict[cube_indx] = cube_obj
        return cube_obj

    def mergeProducts(self):
        'Calculate the top-N derivations by lazily finding the sum of log probs (equivalent to product of probs)'

        # Initializations
        heap_indx = 0
        cb_pop_count = 0
        mP_candLst = []

        for cube_indx, cube_obj in self.cubeDict.iteritems():
            mP_candTup = ()
            mP_candTup = Cube.getBestItem(cube_obj, cube_indx)
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
                entry_exists = Lazy.indexHypothesis(mP_entry_obj.tgt, Hypothesis.getScoreSansLM(mP_entry_obj), h_indx)
                if (entry_exists is None or not settings.opts.use_unique_nbest):
                    mP_entry_obj.inf_cell = Lazy.cell_span
                    if self.cbp_diversity > 0: self.recordDiversity(cube_indx)
                    heapq.heappush(self.coverageHeap, (h_score, h_indx, mP_entry_obj, cube_indx, mP_r))
                elif entry_exists == -1:
                    pass
                else:
                    curr_h_indx = self.getItemIndxInHeap(entry_exists)
                    if self.cbp_diversity > 0: self.recordDiversity(cube_indx, self.coverageHeap[curr_h_indx][3])
                    self.coverageHeap[curr_h_indx] = (h_score, entry_exists, mP_entry_obj, cube_indx, mP_r)

            if cb_pop_count >= self.bsize and (self.cbp_diversity == 0 or ( self.cbp_diversity > 0 and \
                self.coverageDict.has_key(cube_indx) and self.coverageDict[cube_indx] >= self.cbp_diversity )):
                continue

            # get the neighbours for the best item from the corresponding cube
            cube_obj = self.cubeDict[cube_indx]
            # @type cube_obj Cube
            neighbours = Cube.xploreNeighbours(cube_obj, cube_indx, mP_r)

            # add the neighbouring entries to the heap
            for mP_candTup in neighbours:
                new_entry_obj = mP_candTup[1]
                if new_entry_obj is None:
                    new_candTup = (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3])
                else:
                    entry_exists = Lazy.checkHypothesis(new_entry_obj.tgt)
                    if entry_exists is None:                        # New hypothesis; add to heap directly
                        new_candTup = (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3])
                        cb_pop_count += 1
                    elif settings.opts.use_unique_nbest:            # Better than existing hypothesis; copy LM info from existing hyp
                        curr_h_indx = self.getItemIndxInHeap(entry_exists)
                        score_w_lmHeu = Hypothesis.recombineEntry(new_entry_obj, self.coverageHeap[curr_h_indx][2])
                        new_candTup = (-score_w_lmHeu, heap_indx, new_entry_obj, mP_candTup[2], mP_candTup[3])
                    else:
                        curr_h_indx = self.getItemIndxInHeap(entry_exists)
                        score_w_lmHeu = Hypothesis.copyLMInfo(new_entry_obj, self.coverageHeap[curr_h_indx][2])
                        new_candTup = (-score_w_lmHeu, heap_indx, new_entry_obj, mP_candTup[2], mP_candTup[3])

                heapq.heappush(mP_candLst, new_candTup)
                candLst_size += 1
                heap_indx += 1

        # Explore new items for increasing diversity (if required)
        if self.cbp_diversity > 0:
            for c_ind in self.cubeDict.keys():
                diversityItems = []
                cube_obj = self.cubeDict[c_ind]
                if not self.coverageDict.has_key(c_ind):
                    diversityItems = Cube.getkItems4Diversity(cube_obj, c_ind, self.cbp_diversity)
                elif self.coverageDict[c_ind] < self.cbp_diversity:
                    diversityItems = Cube.getkItems4Diversity(cube_obj, c_ind, self.cbp_diversity - self.coverageDict[c_ind])
                else: continue

                for mP_candTup in diversityItems:
                    new_entry_obj = mP_candTup[1]
                    entry_exists = Lazy.checkHypothesis(new_entry_obj.tgt)
                    if entry_exists is None:                        # New hypothesis; add to heap directly
                        new_candTup = (mP_candTup[0], heap_indx, mP_candTup[1], mP_candTup[2], mP_candTup[3])
                    elif settings.opts.use_unique_nbest:            # Better than existing hypothesis; copy LM info from existing hyp
                        curr_h_indx = self.getItemIndxInHeap(entry_exists)
                        score_w_lmHeu = Hypothesis.recombineEntry(new_entry_obj, self.coverageHeap[curr_h_indx][2])
                        new_candTup = (-score_w_lmHeu, heap_indx, new_entry_obj, mP_candTup[2], mP_candTup[3])
                    else:
                        curr_h_indx = self.getItemIndxInHeap(entry_exists)
                        score_w_lmHeu = Hypothesis.copyLMInfo(new_entry_obj, self.coverageHeap[curr_h_indx][2])
                        new_candTup = (-score_w_lmHeu, heap_indx, new_entry_obj, mP_candTup[2], mP_candTup[3])

                    heapq.heappush(self.coverageHeap, new_candTup)
                    heap_indx += 1

        Nbest_size = 0
        NbestLst = []
        self.coverageDict = {}
        heapq.heapify(self.coverageHeap)
        while self.coverageHeap:
            (h_score, h_indx, mP_entry_obj, cube_indx, mP_r) = heapq.heappop( self.coverageHeap )
            if ( Nbest_size < self.bsize or (Nbest_size >= self.bsize and self.cbp_diversity > 0 and \
                (not self.coverageDict.has_key(cube_indx) or self.coverageDict[cube_indx] < self.cbp_diversity)) ):
                NbestLst.append( mP_entry_obj )
                Nbest_size += 1

                if self.cbp_diversity > 0:
                    if self.coverageDict.has_key(cube_indx): self.coverageDict[cube_indx] += 1
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
        if hyp.endswith("</s>"): hyp = hyp[:-5]
        return RefPhrases.isValidRefPhrNSent(cls.sent_id, hyp)


class Cube(object):
    __slots__ = "dimensions", "src_side", "spanT", "ruleLst", "initDimVec", "trackCubeDict", "depth_hier"

    def __init__(self):
        '''Initializes the Cube surface'''

        self.dimensions = 0
        self.src_side = ''
        self.spanT = ()
        self.ruleLst = []
        self.initDimVec = []
        self.trackCubeDict = {}                               # dictionay that tracks the filled boxes in the cube

    def __del__(self):
        '''Clear the rule and feature lists'''

        self.dimensions = 0
        self.spanT = ()
        del self.ruleLst[:]
        del self.trackCubeDict

    def setSourceSide(self, src_rule, spanTup, cube_depth_hier):
        '''Sets the source side rule and span tuple for the current cube'''

        self.src_side = src_rule
        self.spanT = spanTup
        self.depth_hier = cube_depth_hier

    def addTuple(self, rLst):
        '''Adds the rule and feature lists to the current cube'''

        self.dimensions += 1
        self.ruleLst[len(self.ruleLst):] = [ rLst[:] ]

    def getBestItem(self, cube_indx):
        '''Get the best item in the Cube and return its derivation'''

        entryLst = []
        indexVector = []
        self.initDimVec = [0] * self.dimensions
        bestItemsLst = []

        # Iterate thro' the tuples: compute log prob of first entry in every tuple and sum them
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

    def getkItems4Diversity(self, cube_indx, k):
        '''Get k additional items for increasing the diversity in the Cube'''

        neighbours = []
        while True:
            new_items_so_far = len(neighbours)
            for r in self.trackCubeDict.keys():
                if self.trackCubeDict[r] == 0: continue         # ignore the closed frontiers

                for div_candTup in self.xploreNeighbours(cube_indx, list(r)):
                    if div_candTup[1] is not None:
                        neighbours.append(div_candTup)

                # We have found 'k' new items for diversity; break and return them
                if len(neighbours) >= k: break

            # If all the entries in the Cube have been explored already Or if it didn't add any new items:
            #   break and return empty list
            if not neighbours or len(neighbours) == new_items_so_far: break

        return neighbours

    def mergeEntries(self, entriesLst, cube_indx):

        # First process the goal: this will be a (regular/glue) rule
        sf_f_obj = sff.initNew(entriesLst[0].lm_heu)
        score = entriesLst[0].getScoreSansLmHeu()

        # Now process the antecedents
        anteTgts = []
        anteSfFeats = []
        anteItemsStates = []
        for ante_ent in entriesLst[1:]:
            score += ante_ent.getScoreSansLmHeu()
            anteTgts.append( ante_ent.tgt )
            anteSfFeats.append( ante_ent.sf_feat )
            anteItemsStates.append( ante_ent.consItems )

        (tgt_hyp, newConsItems) = lmm.helperConsItem(Lazy.is_last_cell, Lazy.cell_type, \
                                    Lazy.cell_span, entriesLst[0].tgt, anteTgts, anteItemsStates)

        if settings.opts.force_decode and not Lazy.candMatchesRef(tgt_hyp):
            return (score, None)                             # Hypothesis wouldn't lead to reference; ignore this

        """
            Get hypothesis status from the classmethod (in Lazy); hypothesis status can take one of these three values:
            -2 : Hyp was not see earlier; create a new entry
            -1 : Hyp was seen earlier but current one has a better score; create a new entry to replace the existing one
             0 : Hyp was seen earlier and has a poor score than the existing one; ignore this
        """
        score_wo_LM = score - sf_f_obj.aggregFeatScore(anteSfFeats)
        hyp_status = Lazy.getHypothesisStatus(tgt_hyp, score_wo_LM)

        """ Should we recombine hypothesis?
            A new hypothesis is always added; query LM for lm-score and create new entry_obj.
            If an identical hypothesis exists then the current hyp is added under below conditions:
            i) the use_unique_nbest flag is False (add new hyp; but use the LM score of the existing one)
            ii) use_unique_nbest is True and the new hyp is better than the existing one.
        """
        if ( hyp_status == -2 ):
            sf_f_obj.helperScore(newConsItems, Lazy.is_last_cell)
            score += sf_f_obj.comp_score
            entry_obj = Hypothesis(score, self.src_side, tgt_hyp, sf_f_obj, self.depth_hier, (), \
                                   entriesLst[0], entriesLst[1:], newConsItems)
        elif ( hyp_status == 0 and settings.opts.use_unique_nbest ):
            entry_obj = None
        else: entry_obj = Hypothesis(score, self.src_side, tgt_hyp, sf_f_obj, self.depth_hier, (), \
                                     entriesLst[0], entriesLst[1:])

        return (score, entry_obj)
