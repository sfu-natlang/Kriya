import sys, time

from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
import settings

class LanguageModelManager(object):

    max_lm_order = 5
    use_srilm = False
    no_dscnt_UNKlm = False
    lmLst = []
    lmWgts = []
    __slots__ = ()

    @classmethod
    def initLMs(cls, tot_lm_feats, lmTupLst, use_srilm=False):
        assert (tot_lm_feats == len(lmTupLst)), \
                "Error: # of LM features does not match the number of LMs specified as lmTupLst"

        cls.use_srilm = use_srilm
        cls.no_dscnt_UNKlm = settings.opts.no_dscnt_UNKlm
        cls.lmLst = []
        cls.lmWgts = []

        for lm_indx in xrange( tot_lm_feats ):
            (lm_order, lm_file) = lmTupLst[lm_indx]
            
            ## ToDo
            ## Add support for language models having different order (currently they have be of same order)
            ## This requires change in storing multiple elided-tgts for each hypothesis
            if lm_indx > 0:
                assert (lm_order == cls.max_lm_order), \
                       "Error: Multiple LMs should all have the same lm-order (for now)"

            cls.max_lm_order = lm_order
            sys.stderr.write( "Loading LM file %s ... \n" % (lm_file) )
            t_beg = time.time()
            if cls.use_srilm: lm = SRILangModel(lm_order, lm_file, settings.opts.elider)
            else: lm = KENLangModel(lm_order, lm_file, settings.opts.elider)
            cls.lmLst.append(lm)
            t_end = time.time()
            sys.stderr.write( "Time taken for loading LM        : %1.3f sec\n\n" % (t_end - t_beg) )


    @classmethod
    def closeLM(cls):    
        '''Calls the __del__ in {SRI/KEN}LangModel to free the LM variable'''

        for lm_obj in cls.lmLst:
            lm_obj = ''

    @classmethod
    def setLMInfo(cls, lmWgtsLst):
        assert (len(cls.lmLst) == len(lmWgtsLst)), \
               "Error: # of LM weights should be the same as that of # of LM features"
        cls.lmWgts = lmWgtsLst[:]

    @classmethod
    def scoreLMFeat(cls, tgt_phr):
        ''' Compute the LM Heuristic score for the target phrase '''

        lmHeu = [0.0 for x in cls.lmLst]
        for tgt_term in tgt_phr.split():
            if tgt_term == 'X__1' or tgt_term == 'X__2': continue
            lm_indx = 0
            for lm_obj in cls.lmLst:
                lmHeu[lm_indx] += lm_obj.queryLM(tgt_term, 1)
                lm_indx += 1

        lm_indx = 0
        lm_score = 0.0
        for lm_H in lmHeu:
            lm_score += (cls.lmWgts[lm_indx] * lm_H)
            lm_indx += 1

        return lm_score

    @classmethod
    def getLMScore(cls, lmFeatVec):
        lm_score = 0.0
        lm_indx = 0
        for lm_val in lmFeatVec:
            lm_score += (cls.lmWgts[lm_indx] * lm_val)
            lm_indx += 1

        return lm_score

    @classmethod
    def copyLMScores(cls, featVecSrc, featVecTgt):
        lm_score = 0.0
        for lm_indx in xrange( len(cls.lmWgts) ):
            frag_lm_score = featVecSrc[lm_indx] - featVecTgt[lm_indx]
            lm_score += (cls.lmWgts[lm_indx] * frag_lm_score)
            featVecTgt[lm_indx] = featVecSrc[lm_indx]

        return lm_score

    @classmethod
    def adjustUNKLMScore(cls, cand_hyp, featVec):
        lm_indx = 0
        lmFeats = []
        for lm_obj in cls.lmLst:
            if cls.no_dscnt_UNKlm: lmFeats.append( str("%g" % featVec[lm_indx]) )
            else: lmFeats.append( str("%g" % (featVec[lm_indx] - lm_obj.calcUNKLMScore(cand_hyp))) )
            lm_indx += 1

        return ' '.join(lmFeats)

    @classmethod
    def helperLM(cls, consItems, is_last_cell, lmFeatVec):
        '''Helper function for computing the two functions p() and q() and scoring'''

        lm_indx = 0
        tot_lm_heu = 0.0
        tot_lm_score = 0.0
        for lm_obj in cls.lmLst:
            cons_item = consItems[lm_indx]
            lm_lprob = 0.0
            new_out_state = cons_item.r_lm_state

            # Computing n-gram LM-score for partial candidate hypotheses
            eTgtLst = cons_item.e_tgt.split(' ')
            if cons_item.e_len < lm_obj.lm_order:
                if cls.use_srilm: lm_H = lm_obj.getLMHeuCost(eTgtLst, cons_item.e_len)
                else: lm_H = lm_obj.getLMHeuCost(cons_item.e_tgt, eTgtLst, cons_item.e_len)
                e_tgt = cons_item.e_tgt
            else:
                # Compute the LM probabilities for all complete m-grams in the elided target string, and
                # Compute heuristic prob for first m-1 terms in target
                if cls.use_srilm:
                    (lm_lprob, e_tgt) = lm_obj.scorePhrnElide(eTgtLst, cons_item.e_len, cons_item.mgramSpans)
                    lm_H = lm_obj.getLMHeuCost(eTgtLst, cons_item.e_len)
                else:
                    (lm_lprob, e_tgt, new_out_state) = lm_obj.scorePhrnElide(eTgtLst, cons_item.e_len, cons_item.mgramSpans, cons_item.statesLst, cons_item.r_lm_state)
                    lm_H = lm_obj.getLMHeuCost(cons_item.e_tgt, eTgtLst, cons_item.e_len)

            if ( is_last_cell ):                                 # lm_heu is added permanently in the last cell
                lm_lprob += lm_H
                lm_H = 0.0

            lmFeatVec[lm_indx] += lm_lprob
            lm_heu = cls.lmWgts[lm_indx] * lm_H
            tot_lm_score += lm_heu + (cls.lmWgts[lm_indx] * lm_lprob)   # Pruning score including LM and heuristic
            tot_lm_heu += lm_heu

            consItems[lm_indx].r_lm_state = new_out_state
            consItems[lm_indx].e_tgt = e_tgt
            lm_indx += 1

        return (tot_lm_score, tot_lm_heu)

    @classmethod
    def helperConsItem(cls, is_last_cell, cell_type, cell_span, \
                        goal_tgt, goalItemStates, anteTgts, anteItemStates):

        consItemStates = []          # List of objects of type 'ConsequentItem'
        lm_indx = 0
        tgt = ''
        prev_tgt = ''
        #if not goalItemStates: goalItemStates = [None]
        for goal_item in goalItemStates:
            anteItems = [x[lm_indx] for x in anteItemStates]
            if goal_item is None: cons_item = ConsequentItem(goal_tgt)
            else: cons_item = ConsequentItem(goal_tgt, goal_item.r_lm_state)
            cons_item.setState(is_last_cell, cell_type, cell_span, goal_tgt, anteTgts, anteItems)
            tgt = cons_item.mergeAntecedents(anteTgts[:], anteItems[:], cls.lmLst[lm_indx])
            if prev_tgt == '':
                prev_tgt = tgt
            assert (prev_tgt == tgt), "The target hypotheses from different LMs are not same: %s :: %s" % (prev_tgt, tgt)
            consItemStates.append(cons_item)
            lm_indx += 1

        return tgt, consItemStates

class ConsequentItem(object):
    """ Class for an Consequent Item (result of merging two antecendents)"""

    __slots__ = "e_tgt", "e_len", "r_lm_state", "statesLst", "mgramSpans"

    def __init__(self, e_tgt, lm_right = None):
        self.e_tgt = e_tgt
        self.e_len = 0
        self.r_lm_state = lm_right
        self.statesLst = []
        self.mgramSpans = []

    def __del__(self):
        '''Clear the data-structures'''

        self.e_tgt = ''
        self.r_lm_state = None
        del self.statesLst
        del self.mgramSpans

    def verify(self, lm_obj, anteItems):
        ''' Verifies the state object by printing the state (for debugging) '''
        if self.r_lm_state is not None: lm_obj.printState(self.r_lm_state)
        else: print "  >> Consequent state : None"
        if len(anteItems) >= 1:
            if anteItems[0].r_lm_state is not None: lm_obj.printState(anteItems[0].r_lm_state)
            else: print "    >>> Antecedent state-1 : None"
        if len(anteItems) == 2:
            if anteItems[1].r_lm_state is not None: lm_obj.printState(anteItems[1].r_lm_state)
            else: print "    >>> Antecedent state-2 : None"

    def setState(self, is_last_cell, cell_type, cell_span, goal_tgt, anteTgts, anteItems):
        '''Set the beginning and end state of the consequent item as a tuple'''

        beg_state = 0
        end_state = 0
        if goal_tgt.startswith('X__1') or goal_tgt.startswith('S__1'): beg_state = 1
        elif goal_tgt.startswith('X__2'): beg_state = 2
        if goal_tgt.endswith('X__1'): end_state = 1
        elif goal_tgt.endswith('X__2'): end_state = 2
        edgeTup = (beg_state, end_state)

        if ( is_last_cell or (cell_span[0] == 0 and cell_type == 'S') ):
            self.addLeftSMarker(goal_tgt, edgeTup, anteTgts)
        if ( is_last_cell ):
            edgeTup = self.addRightSMarker(goal_tgt, edgeTup, anteTgts)
        self.setLMState(edgeTup, anteItems)

    def addLeftSMarker(self, goal_tgt, edgeTup, anteTgts):
        '''Add the left sentence marker and also adjust offsets to reflect this'''

        if (edgeTup[0] == 0 and not goal_tgt.startswith('<s>')) \
            or (edgeTup[0] == 1 and not anteTgts[0].startswith('<s>')) \
            or (edgeTup[0] == 2 and not anteTgts[1].startswith('<s>')):
                #goal_tgt = '<s> ' + goal_tgt
                self.e_tgt = '<s> ' + self.e_tgt

    def addRightSMarker(self, goal_tgt, edgeTup, anteTgts):
        '''Add the right sentence marker'''

        if (edgeTup[1] == 0 and not goal_tgt.endswith('</s>')) \
            or (edgeTup[1] == 1 and not anteTgts[0].endswith('</s>')) \
            or (edgeTup[1] == 2 and not anteTgts[1].endswith('</s>')):
                #goal_tgt = goal_tgt + ' </s>'
                self.e_tgt = self.e_tgt + ' </s>'
                self.r_lm_state = None
                if edgeTup[1] != 0: edgeTup = (edgeTup[0], 0)

        return edgeTup

    def setLMState(self, edgeTup, anteItems):
        '''Set the right LM state for the consequent item'''

        if self.r_lm_state is not None: pass
        elif edgeTup[1] == 1:
            self.r_lm_state = anteItems[0].r_lm_state
        elif edgeTup[1] == 2:
            self.r_lm_state = anteItems[1].r_lm_state

    def mergeAntecedents(self, anteTgts, anteItems, lm_obj):

        self.e_len = 0
        self.statesLst = []
        self.mgramSpans = []
        mgram_beg = 0
        eTgtLst = []
        tgtItems = []
        curr_state = None

        for term in self.e_tgt.split():
            if term == "X__1" or term == "S__1":
                tgtItems.append( anteTgts[0] )
                tempLst = anteItems[0].e_tgt.split()
                next_state = anteItems[0].r_lm_state
            elif term == "X__2":
                tgtItems.append( anteTgts[1] )
                tempLst = anteItems[1].e_tgt.split()
                next_state = anteItems[1].r_lm_state
            else:
                tgtItems.append( term )
                eTgtLst.append(term)
                self.e_len += 1
                continue

            for ante_term in tempLst:
                if ante_term == settings.opts.elider:
                    if (self.e_len - mgram_beg >= lm_obj.lm_order \
                            or curr_state is not None) and mgram_beg != self.e_len:
                        self.mgramSpans.append( (mgram_beg, self.e_len) )
                        self.statesLst.append( curr_state )
                    curr_state = next_state
                    if settings.opts.no_lm_state: mgram_beg = self.e_len + 1
                    else: mgram_beg = self.e_len + lm_obj.lm_order
                eTgtLst.append(ante_term)
                self.e_len += 1

        if (self.e_len - mgram_beg >= lm_obj.lm_order \
                or curr_state is not None) and mgram_beg != self.e_len:
            self.mgramSpans.append( (mgram_beg, self.e_len) )
            self.statesLst.append( curr_state )

        self.e_tgt = ' '.join(eTgtLst)
        return ' '.join(tgtItems)
