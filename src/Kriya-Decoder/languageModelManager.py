import sys, time

from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
import settings

class LanguageModelManager(object):

    max_lm_order = 5
    lm_offset = None
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
    def setLMInfo(cls, lm_offset, lmWgtsLst):
        assert (len(cls.lmLst) == len(lmWgtsLst)), \
               "Error: # of LM weights should be the same as that of # of LM features"
        cls.lm_offset = lm_offset
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
    def getLMScore(cls, featVec):
        lm_score = 0.0
        for lm_indx in xrange( len(cls.lmWgts) ):
            lm_score += (cls.lmWgts[lm_indx] * featVec[cls.lm_offset + lm_indx])

        return lm_score

    @classmethod
    def copyLMScores(cls, featVecSrc, featVecTgt):
        lm_score = 0.0
        for lm_indx in xrange( len(cls.lmWgts) ):
            frag_lm_score = featVecSrc[cls.lm_offset + lm_indx] - featVecTgt[cls.lm_offset + lm_indx]
            lm_score += (cls.lmWgts[lm_indx] * frag_lm_score)
            featVecTgt[cls.lm_offset + lm_indx] = featVecSrc[cls.lm_offset + lm_indx]

        return lm_score, featVecTgt[:]

    @classmethod
    def adjustUNKLMScore(cls, cand_hyp, featVec):
        lm_indx = 0
        lmFeats = []
        for lm_obj in cls.lmLst:
            if cls.no_dscnt_UNKlm: lmFeats.append( str(featVec[cls.lm_offset + lm_indx]) )
            else: lmFeats.append( str(featVec[cls.lm_offset + lm_indx] - lm_obj.calcUNKLMScore(cand_hyp)) )
            lm_indx += 1

        return ' '.join(lmFeats)

    @classmethod
    def helperLM(cls, score, cons_item, is_last_cell, featVec):
        '''Helper function for computing the two functions p() and q() and scoring'''

        new_out_state = cons_item.r_lm_state

        lm_indx = 0
        tot_lm_heu = 0.0
        for lm_obj in cls.lmLst:
            lm_lprob = 0.0
            # Computing n-gram LM-score for partial candidate hypotheses
            if cons_item.e_len < lm_obj.lm_order:
                if cls.use_srilm: lm_H = lm_obj.getLMHeuCost(cons_item.eTgtLst, cons_item.e_len)
                else: lm_H = lm_obj.getLMHeuCost(cons_item.e_tgt, cons_item.eTgtLst, cons_item.e_len)
                e_tgt = cons_item.e_tgt
            else:
                # Compute the LM probabilities for all complete m-grams in the elided target string, and
                # Compute heuristic prob for first m-1 terms in target
                if cls.use_srilm:
                    (lm_lprob, e_tgt) = lm_obj.scorePhrnElide(cons_item.eTgtLst, cons_item.e_len, cons_item.mgramSpans)
                    lm_H = lm_obj.getLMHeuCost(cons_item.eTgtLst, cons_item.e_len)
                else:
                    (lm_lprob, e_tgt, new_out_state) = lm_obj.scorePhrnElide(cons_item.eTgtLst, cons_item.e_len, cons_item.mgramSpans, cons_item.statesLst, cons_item.r_lm_state)
                    lm_H = lm_obj.getLMHeuCost(cons_item.e_tgt, cons_item.eTgtLst, cons_item.e_len)

            if ( is_last_cell ):                                 # lm_heu is added permanently in the last cell
                lm_lprob += lm_H
                lm_H = 0.0

            featVec[cls.lm_offset + lm_indx] += lm_lprob
            lm_heu = cls.lmWgts[lm_indx] * lm_H
            score += lm_heu + (cls.lmWgts[lm_indx] * lm_lprob)   # Pruning score including LM and heuristic
            tot_lm_heu += lm_heu
            lm_indx += 1

        return (score, tot_lm_heu, featVec[:], e_tgt, new_out_state)
