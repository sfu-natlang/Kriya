## @author baskaran

import sys

class RefPhrases(object):
    '''Reference Phrases class for the phrases in the reference(s)'''

    tot_ref_phrases = 0
    phrasesDict = {}
    sentPhrasesDoD = {}
    startPhrasesDoD = {}
    refDict = {}

    def __init__(self, sent_id, refFiles):
        '''Loading rules from the phrase table and initializing their feature values'''

        self.loadReferencePhrases(sent_id, refFiles)

    #def __del__(self):
        #del RefPhrases.phrasesDict
        #del RefPhrases.sentPhrasesDoD

    def loadReferencePhrases(self, sent_id, refFiles):
        '''Loads the phrases in the reference(s)'''

        sys.stderr.write( "Loading Reference phrases for forced decoding mode ...\n" )
        refHLst = [ open(file, 'r') for file in refFiles ]

        for file_i, refH in enumerate( refHLst ):
            sys.stderr.write( " * Loading ref phrases from file : %s\n" % (refFiles[file_i]) )

            sent_i = sent_id
            for sent in refH:
                sent = sent.strip()
                if sent_i not in RefPhrases.refDict: RefPhrases.refDict[sent_i] = []
                RefPhrases.refDict[sent_i].append(sent)
                self.xtractPhrases(sent_i, sent)
                sent_i += 1
        refH.close()

    def xtractPhrases(self, sent_i, sent):
        '''Extract the phrases from the reference sentence and index them'''

        refToks = sent.split()
        sent_len = len(refToks)

        if not RefPhrases.sentPhrasesDoD.has_key(sent_i):
            RefPhrases.sentPhrasesDoD[sent_i] = {}
            RefPhrases.startPhrasesDoD[sent_i] = {}

        for ref_j in xrange(sent_len):
            for ref_k in xrange(ref_j + 1, sent_len + 1):
                ref_phr = ' '.join( refToks[ref_j:ref_k] )

                # Add phrases directly to the dict
                if RefPhrases.phrasesDict.has_key(ref_phr):
                    RefPhrases.phrasesDict[ref_phr] += 1
                else:
                    RefPhrases.phrasesDict[ref_phr] = 1
                    RefPhrases.tot_ref_phrases += 1

                # Add phrases to the dict indexed by the sent id
                if not RefPhrases.sentPhrasesDoD[sent_i].has_key(ref_phr):
                    RefPhrases.sentPhrasesDoD[sent_i][ref_phr] = 1
                # Add starting phrases to a dict indexed by the sent id
                if ref_j == 0:
                    RefPhrases.startPhrasesDoD[sent_i][ref_phr] = 1
        return None

    @classmethod
    def isValidRefPhr(cls, ref_phr):
        return cls.phrasesDict.has_key(ref_phr)

    @classmethod
    def isValidRefPhrNSent(cls, sent_id, ref_phr):
        if not cls.sentPhrasesDoD.has_key(sent_id):
            sys.stderr.write("Invalid sent_id %d provided. Exiting!!\n" % (sent_id))
            sys.exit(1)

        return cls.sentPhrasesDoD[sent_id].has_key(ref_phr)

    @classmethod
    def isValidRefPhrStart(cls, sent_id, ref_phr):
        if not cls.startPhrasesDoD.has_key(sent_id):
                sys.stderr.write("Invalid sent_id %d provided. Exiting!!\n" % (sent_id))
                sys.exit(1)
        return cls.startPhrasesDoD[sent_id].has_key(ref_phr)

    @classmethod
    def isValidRefSent(cls, sent_id, ref_phr):
            if not cls.refDict.has_key(sent_id):
                sys.stderr.write("Invalid sent_id %d provided. Exiting!!\n" % (sent_id))
                sys.exit(1)
            for ref_sent in cls.refDict[sent_id]: 
                if ref_sent.strip() == ref_phr.strip():
                    return True
            return False
        
    @classmethod
    def printRefPhrases(cls, sent_id):
        '''Prints the reference phrases found in the references for a given sent id (for debugging)'''

        for ref_phr in cls.sentPhrasesDoD.keys(sent_id):
            sys.stderr.write("Reference phrase: %d\n" % (ref_phr))

        return None
