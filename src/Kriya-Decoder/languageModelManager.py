import sys, time

from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
import settings

class LanguageModelManager(object):

    debug = False
    use_srilm = False
    no_dscnt_UNKlm = False
    lmLst = []
    lmWgts = []
    __slots__ = ()

    @classmethod
    def initLMs(cls, tot_lm_feats, lmTupLst, use_srilm=False):
        assert (tot_lm_feats == len(lmTupLst)), \
                "Error: # of LM features does not match the number of LMs specified as lmTupLst"

        cls.debug = settings.opts.debug
        cls.use_srilm = use_srilm
        cls.no_dscnt_UNKlm = settings.opts.no_dscnt_UNKlm
        cls.lmLst = []
        cls.lmWgts = []

        for lm_indx in xrange( tot_lm_feats ):
            (lm_order, lm_file) = lmTupLst[lm_indx]
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
            #frag_lm_score = featVecSrc[lm_indx] - featVecTgt[lm_indx]
            #lm_score += (cls.lmWgts[lm_indx] * frag_lm_score)
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

            # Computing n-gram LM-score for partial candidate hypotheses
            if cons_item.e_len < lm_obj.lm_order:
                if cls.use_srilm: lm_H = lm_obj.getLMHeuCost(cons_item.eTgtLst, cons_item.e_len)
                else: lm_H = lm_obj.getLMHeuCost(cons_item)
            else:
                # Compute the LM probabilities for all complete m-grams in the elided target string, and
                # Compute heuristic prob for first m-1 terms in target
                if cls.use_srilm:
                    (lm_lprob, eTgtLst) = lm_obj.scorePhrnElide(cons_item.eTgtLst, cons_item.e_len, cons_item.mgramSpans)
                    lm_H = lm_obj.getLMHeuCost(cons_item.eTgtLst, cons_item.e_len)
                else:
                    lm_lprob = lm_obj.scoremGrams(cons_item.phrStateTupLst)
                    lm_H = lm_obj.getLMHeuCost(cons_item)

            if ( is_last_cell ):                                 # lm_heu is added permanently in the last cell
                if cons_item.new_elided_tgt: lm_lprob += lm_H
                lm_H = 0.0

            lmFeatVec[lm_indx] += lm_lprob
            tot_lm_heu += (cls.lmWgts[lm_indx] * lm_H)           # Heuristic LM score (pruning score is the sum of heuristic score and lm comp score so far)
            if cons_item.new_elided_tgt:
                tot_lm_score += (cls.lmWgts[lm_indx] * lm_lprob) # LM score for the m-grams in this hypothesis
            lm_indx += 1

        return (tot_lm_score, tot_lm_heu)

    @classmethod
    def helperConsItem(cls, is_last_cell, cell_type, cell_span, \
                        goalTgt, anteHyps, anteItemStates):

        anteTgts = []
        for tgt in anteHyps:
            anteTgts.append( tgt.split() )

        tgt = ''
        lm_indx = 0
        consItemStates = []          # List of objects of type 'ConsequentItem'
        for lm_obj in cls.lmLst:
            anteItems = [x[lm_indx] for x in anteItemStates]
            cons_item = ConsequentItem(goalTgt)
            cons_item.setStateNMerge(is_last_cell, cell_type, cell_span, anteTgts, anteItems)
            tgt = cons_item.mergeAntecedents(anteHyps, anteItems, lm_obj.lm_order, lm_obj)
            if LanguageModelManager.debug:
                if lm_indx > 0:
                    assert (prev_tgt == tgt), "The target hypotheses from different LMs are not same: %s :: %s" % (prev_tgt, tgt)
                prev_tgt = tgt
            consItemStates.append(cons_item)
            lm_indx += 1

        return tgt, consItemStates

class ConsequentItem(object):
    """ Class for an Consequent Item (result of merging two antecendents)"""

    __slots__ = "e_len", "r_lm_state", "eTgtLst", "phrStateTupLst", "new_elided_tgt"

    def __init__(self, goalTgt):
        self.e_len = 0
        self.r_lm_state = None
        self.eTgtLst = goalTgt[:]
        self.phrStateTupLst = []
        self.new_elided_tgt = True

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

    def setStateNMerge(self, is_last_cell, cell_type, cell_span, anteTgts, anteItems):
        '''Set the beginning and end state of the consequent item as a tuple'''

        beg_state = 0
        end_state = 0
        if self.eTgtLst[0] == 'X__1' or self.eTgtLst[0] == 'S__1': beg_state = 1
        elif self.eTgtLst[0] == 'X__2': beg_state = 2
        if self.eTgtLst[-1] == 'X__1': end_state = 1
        elif self.eTgtLst[-1] == 'X__2': end_state = 2
        edgeTup = (beg_state, end_state)

        if ( is_last_cell or (cell_span[0] == 0 and cell_type == 'S') ):
            self.addLeftSMarker(edgeTup, anteTgts)
        if ( is_last_cell ):
            edgeTup = self.addRightSMarker(edgeTup, anteTgts)
        self.setLMState(edgeTup, anteItems)

    def addLeftSMarker(self, edgeTup, anteTgts):
        '''Add the left sentence marker and also adjust offsets to reflect this'''

        if (edgeTup[0] == 0 and not self.eTgtLst[0] == '<s>') \
            or (edgeTup[0] == 1 and not anteTgts[0][0] == '<s>') \
            or (edgeTup[0] == 2 and not anteTgts[1][0] == '<s>'):
                self.eTgtLst.insert(0, '<s>')

    def addRightSMarker(self, edgeTup, anteTgts):
        '''Add the right sentence marker'''

        if (edgeTup[1] == 0 and not self.eTgtLst[-1] == '</s>') \
            or (edgeTup[1] == 1 and not anteTgts[0][-1] == '</s>') \
            or (edgeTup[1] == 2 and not anteTgts[1][-1] == '</s>'):
                self.eTgtLst.append('</s>')
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

    def mergeAntecedents(self, anteHyps, anteItems, lm_order, lm_obj):

        mgram_beg = 0
        e_new_len = 0
        eTgtLstNew = []
        tgtItems = []
        phrStateTupLst = []
        curr_state = None
        old_e_tgt = ''

        for term in self.eTgtLst:
            if term == "X__1" or term == "S__1":
                tgtItems.append(anteHyps[0])
                tempLst = anteItems[0].eTgtLst
                old_e_tgt = ' '.join(tempLst)
                next_state = anteItems[0].r_lm_state
            elif term == "X__2":
                tgtItems.append(anteHyps[1])
                tempLst = anteItems[1].eTgtLst
                next_state = anteItems[1].r_lm_state
            else:
                tgtItems.append(term)
                eTgtLstNew.append(term)
                e_new_len += 1
                continue

            eTgtLstNew.extend(tempLst)
            mgram_beg, curr_state = self.handleEdges(lm_order, mgram_beg, e_new_len, curr_state, next_state, tempLst, eTgtLstNew)
            e_new_len += len(tempLst)

        self.elideNewTgt(old_e_tgt, lm_obj, lm_order, mgram_beg, e_new_len, curr_state, eTgtLstNew)
        return ' '.join(tgtItems)

    def elideNewTgt(self, old_e_tgt, lm_obj, lm_order, mgram_beg, e_new_len, curr_state, eTgtLstNew):
        if mgram_beg != e_new_len and (curr_state is not None \
                or e_new_len - mgram_beg >= lm_order):
            self.phrStateTupLst.append( (' '.join( eTgtLstNew[mgram_beg:e_new_len] ), curr_state) )

        # Finally elide the string again and compute the right LM state if required
        if e_new_len < lm_order:
            self.eTgtLst = eTgtLstNew
        else:
            if self.r_lm_state is None and not settings.opts.no_lm_state:
                self.r_lm_state = lm_obj.getLMState(' '.join( eTgtLstNew[-lm_order:] ))
            self.eTgtLst = eTgtLstNew[0:lm_order-1] + [lm_obj.elider] + eTgtLstNew[1-lm_order:]
        self.e_len = len(self.eTgtLst)
        if old_e_tgt == ' '.join(self.eTgtLst):
            self.new_elided_tgt = False

    def handleEdges(self, lm_order, mgram_beg, curr_e_len, curr_state, next_state, tempLst, eTgtLstNew):
        for ante_term in tempLst:
            if ante_term != settings.opts.elider:
                curr_e_len += 1
                continue
            if (curr_e_len - mgram_beg >= lm_order \
                    or curr_state is not None) and mgram_beg != curr_e_len:
                self.phrStateTupLst.append( (' '.join( eTgtLstNew[mgram_beg:curr_e_len] ), curr_state) )
            curr_state = next_state
            if settings.opts.no_lm_state: mgram_beg = curr_e_len + 1
            else: mgram_beg = curr_e_len + lm_order
            break

        return mgram_beg, curr_state

