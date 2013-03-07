import math, sys

from languageModelManager import LanguageModelManager
import settings

class FeatureManager(object):
    '''Weights for the different features in the log-linear model''' 

    lm = []
    tm = []
    glue = 0.0
    wp = 0.0
    lm_offset = 0
    wp_offset = 0
    glue_offset = 0
    egivenf_offset = 0
    lmInitLst = []
    unkRuleTup = ()
    pp_val = math.log(2.718)
    log_normalizer = 0.434294

    __slots__ = ()

    @classmethod
    def setFeatureWeights(cls, tot_lm_feats, tot_tm_feats, how_many_tm_feats):
        assert (tot_lm_feats == len(cls.lm)), "Error: Language model param should have %d weights instead of %d" % (tot_lm_feats, len(cls.lm))
        assert (tot_tm_feats == len(cls.tm)), "Error: Translation model param should have %d weights instead of %d" % (tot_tm_feats, len(cls.tm))
        for tmVec in cls.tm:
            assert (how_many_tm_feats == len(tmVec)), "Error: # of TM features (%d) doesn't match TM weights count (%d)" % (how_many_tm_feats, len(tmVec))

        cls.setFeatureIndices()
        cls.setUnkRule()
        cls.printWeights()
        LanguageModelManager.setLMInfo(cls.lm_offset, cls.lm)

    @classmethod
    def setFeatureIndices(cls):
        cls.lm_offset = len(cls.tm) * len(cls.tm[0])
        cls.wp_offset = -2
        cls.glue_offset = -1
        cls.egivenf_offset = 2
        cls.lmInitLst = [0.0 for x in xrange( len(cls.lm) )]

    @classmethod
    def setUnkRule(cls):
        unkFeatVec = []
        for tm_indx in xrange( len(cls.tm) ):
            unkFeatVec = [0.0 for x in cls.tm[tm_indx]]

        unkFeatVec += [0.0 for x in xrange( len(cls.lm) )] + [-1, 0.0]
        p_score = cls.scorePTEntry(unkFeatVec)
        cls.unkRuleTup = (p_score, 0.0, unkFeatVec)

    @classmethod
    def printWeights(cls):
        for tm_indx in xrange( len(cls.tm) ):
            tm_wgts_str = ' '.join( [str(x) for x in cls.tm[tm_indx]] )
            sys.stdout.write( "TM-%d weights   : [%s]\n" % (tm_indx, tm_wgts_str) )
        for lm_indx in xrange( len(cls.lm) ):
            sys.stdout.write( "LM-%d weights   : %g\n" % (lm_indx, cls.lm[lm_indx]) )
        sys.stdout.write( "Word penalty and Glue feature weights   : %g %g\n" % (cls.wp, cls.glue) )

    @classmethod
    def buildFeatVec(cls, probs, term_count):
        '''Build the feature vector from a string of probs and add to it phrase & word penalty and glue score'''
    
        ## All feature values must be represented as log-probs in base 'e' ##
        ## Any log-prob in base '10' must be converted to base 'e' by dividing it by math.log10(math.exp(1)) ##
        featVec = []

        # add the TM features
        featVec = [float(x) for x in probs.split()]        # Already in base-e log-prob

        # add phrase penalty and word penalty to the featVec
        featVec += [cls.pp_val] + cls.lmInitLst + [-term_count, 0.0]

        return featVec

    @classmethod
    def scorePTEntry(cls, featVec):
        p_score = 0.0
        for tm_indx in xrange( len(cls.tm) ):
            tm_offset = tm_indx * len( cls.tm[tm_indx] )
            for tm_feat_indx in xrange( len(cls.tm[tm_indx]) ):
                p_score += (cls.tm[tm_indx][tm_feat_indx] * featVec[tm_offset + tm_feat_indx])

        p_score += (cls.wp * featVec[cls.wp_offset]) + (cls.glue * featVec[cls.glue_offset])

        return p_score

    @classmethod
    def scoreHypothesis(cls, featVec):
        p_score = 0.0
        for tm_indx in xrange( len(cls.tm) ):
            tm_offset = tm_indx * len( cls.tm[tm_indx] )
            for tm_feat_indx in xrange( len(cls.tm[tm_indx]) ):
                p_score += (cls.tm[tm_indx][tm_feat_indx] * featVec[tm_offset + tm_feat_indx])

        for lm_indx in xrange( len(cls.lm) ):
            p_score += (cls.lm[lm_indx] * featVec[cls.lm_offset + lm_indx])

        p_score += (cls.wp * featVec[cls.wp_offset]) + (cls.glue * featVec[cls.glue_offset])

        return p_score

    @classmethod
    def getIndxGlue(cls):
        return cls.glue_offset

    @classmethod
    def getIndxP_ef(cls):
        return cls.egivenf_offset

    @classmethod
    def formatFeatureVals(cls, cand_hyp, fVec):

        tmFeats = []
        for tm_indx in xrange( len(cls.tm) ):
            tm_beg = tm_indx * len( cls.tm[tm_indx] )
            tm_end = tm_beg + len( cls.tm[tm_indx] )
            tm_str = ' '.join( [str(x) for x in fVec[tm_beg:tm_end]] )
            tmFeats.append(tm_str)
        tm_str = ' '.join(tmFeats)
        lm_str = LanguageModelManager.adjustUNKLMScore(cand_hyp, fVec)
        wp_str = str(fVec[cls.wp_offset])
        glue_str = str(fVec[cls.glue_offset])

        if (settings.opts.no_glue_penalty):
            feats = ['lm:', 'wp:', 'tm:']
            if (settings.opts.zmert_nbest):
                feat_str = ' '.join( [lm_str, wp_str, tm_str] )
            else:
                feat_str = ' '.join( map(lambda x,y: x+' '+y, feats, [lm_str, wp_str, tm_str]) )
        else:
            feats = ['lm:', 'glue:', 'wp:', 'tm:']
            if (settings.opts.zmert_nbest):
                feat_str = ' '.join( [lm_str, glue_str, wp_str, tm_str] )
            else:
                feat_str = ' '.join( map(lambda x,y: x+' '+y, feats, [lm_str, glue_str, wp_str, tm_str]) )

        return feat_str
