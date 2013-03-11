import sys

from languageModelManager import LanguageModelManager as lmm

class StatelessFeatures(object):
    __slots__ = "tmFVec", "wp", "glue"
    
    def __init__(self, tmFeats, wp_val, glue_val = 0.0):
        self.tmFVec = tmFeats[:]
        self.wp = wp_val
        self.glue = glue_val

    @classmethod
    def copySLFeat(cls, other):
        return StatelessFeatures(other.tmFVec, other.wp, other.glue)

    def aggregFeatScore(self, other):
        # Aggregate the feature values of the stateless feats of antecendts with that of inference item
        indx = 0
        for tm_f_val in other.tmFVec:
            self.tmFVec[indx] += tm_f_val
            indx += 1

        self.wp += other.wp
        self.glue += other.glue

    def stringifyMembers(self):
        return ' '.join( [str("%g" % x) for x in self.tmFVec] ), str("%g" % self.wp), str("%g" % self.glue)


class StatefulFeatures(object):
    
    lmInitLst = []
    __slots__ = "lmFVec", "lm_heu", "comp_score"

    def __init__(self, lmFeats, sful_score = 0.0, lm_heu = 0.0):
        self.lmFVec = lmFeats[:]
        self.comp_score = sful_score
        self.lm_heu = lm_heu

    @classmethod
    def initNew(cls, lm_heu):
        return StatefulFeatures(StatefulFeatures.lmInitLst[:], 0.0, lm_heu)

    @classmethod
    def setLMInitLst(cls, tot_lm_feats):
        StatefulFeatures.lmInitLst = [0.0 for x in xrange(tot_lm_feats)]

    @classmethod
    def copySFFeat(cls, other):
        return StatefulFeatures(other.lmFVec, other.comp_score)

    def copyNScoreDiff(self, other):
        lm_score_diff = lmm.copyLMScores(other.lmFVec, self.lmFVec)
        self.lm_heu = other.lm_heu
        self.comp_score += lm_score_diff
        return lm_score_diff

    def getLMHeu(self):
        return self.lm_heu

    def aggregFeatScore(self, anteSfLst):
        # Aggregate the feature values of the stateful feats of antecendts with that of inference item
        for ante_sf_obj in anteSfLst:
            indx = 0
            for ante_fval in ante_sf_obj.lmFVec:
                self.lmFVec[indx] += ante_fval
                indx += 1

        # Now return the score of stateful features
        return lmm.getLMScore(self.lmFVec)

    def getStateScore(self):
        return self.lm_heu + lmm.getLMScore(self.lmFVec)

    def helperScore(self, newConsItems, is_last_cell):
        (lm_comp_score, lm_comp_heu) = lmm.helperLM(newConsItems, is_last_cell, self.lmFVec)
        self.comp_score += lm_comp_score
        self.lm_heu = lm_comp_heu

    def stringifyMembers(self, cand_hyp):
        return lmm.adjustUNKLMScore(cand_hyp, self.lmFVec)