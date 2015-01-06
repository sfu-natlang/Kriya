# Synchronous CFG based Decoder for Machine Translation #

import operator
import os.path
import sys
import time

import settings
from cell import Cell
from lattice import Lattice
from entry_CP import getInitHyp
from lazyMerge_CP import Lazy
from phraseTable import PhraseTable
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
from refPhrases import RefPhrases

def decode_CP(sent_indx, lattice_obj):
    final_cell = False
    # Phase-1: Initialization
    chart = [Cell() for i in range(lattice_obj.sent_len+1)]
    # Fill the initial stack (or chartDict) with null hypothesis 
    p_i = 0
    ## log
    #print "\nFilling stack:", p_i
    chart[0].flush2Cell([getInitHyp(lattice_obj.sent_len)])     # Flush the entries to the cell
    ## log print hypotheses in this stack

    # Phase-2: Filling the stacks
    # Iterate through all stacks each corresponds to number of covered words (1,sent_len)
    total_cubes = 0
    total_groups = 0
    for p_s in range(1, lattice_obj.sent_len+1):
	## log
	#print "\nFilling stack:", p_s
	if ( p_s == lattice_obj.sent_len ):
	    final_cell = True
	cube_indx = 0
	merge_obj = Lazy(sent_indx, p_s, final_cell)
	for p_j in range(max(0, p_s - settings.opts.fr_rule_terms), p_s):
	    p_l = p_s - p_j
	    ## log
	    #print "\nFilling stack:", p_s, "\tSpan length:", p_l
	    for group_sign in chart[p_j].table:
		unc_span = group_sign.first_span
		lattice_obj.matchRule(unc_span)
		hypsLst = chart[p_j].getHyps(group_sign) 
		## log: print the group of hypotheses for span: unc_span
		for src_rule in Lattice.ruleLookUpTable[unc_span].get(p_l, []):
		    # set the source side rule and span for the current cube
		    spanLst = Lattice.spanToRuleDict[unc_span][src_rule]
		    Lazy.setSourceInfo( merge_obj, cube_indx, src_rule, unc_span, spanLst, 0)
		    #print "new Cube:", cube_indx, src_rule, unc_span, spanLst
		    # add the hypothesis list to the cube as its first dimension
		    Lazy.add2Cube(merge_obj, cube_indx, hypsLst)
		    # add the rule list to the cube as its second dimension
		    Lazy.add2Cube(merge_obj, cube_indx, Lattice.ruleLookUpTable[unc_span][p_l][src_rule])
		    ## add log information in the cube
		    cube_indx += 1

	total_cubes += cube_indx
	tgtLst = Lazy.mergeProducts(merge_obj)
	chart[p_s].flush2Cell(tgtLst)   # Flush the entries to the cell
	merge_obj = ''  # Important: This clears the mem-obj and calls the garbage collector on Lazy()
	total_groups += len(chart[p_s].table)
	
	## log 
	#print "\n\n Stack:", p_s, "\tnew hyps:"
	#for hyp in tgtLst:
        #    print hyp.printPartialHyp()
	#if settings.opts.force_decode:
	#    if len(tgtLst) == 0:
	#        sys.stderr.write("           INFO  :: Force decode mode: No matching candidate found for cell (0, %d).\n" % (p_s))
	#print "stack:\t", p_s, " has ", cube_indx, ' cubes and ', len(chart[p_s].table), " groups"

    #print "sent len:  ", self.sent_len, "\t\tavg cubes:  %1.3g\t\tavg groups:  %1.3g" % ((total_cubes*1.0)/self.sent_len, (total_groups*1.0)/self.sent_len )
    if len(chart[p_s]) == 0:
	if settings.opts.force_decode: sys.stderr.write("           INFO  :: Force decode mode: No matching candidate found.")
	else:  sys.stderr.write("           INFO  :: Error in Decoding: No matching candidate found.")
	return 0
    chart[p_s].printNBest(None, sent_indx)       # Print the N-best derivations in the last cell
    if settings.opts.trace_rules > 0:
        chart[p_s].printTrace(self.sent)        # Prints the translation trace for the top-3 entries
    return 1

def readNParse(sent_count):
    '''Parse the sentences in the array'''

    sent_indx = 0
    coverage_cnt = 0
    relaxed_decoding = False
    refsLst = []

    tot_time = 0.0
    inF = open(settings.opts.inFile, 'r')
    sys.stderr.write( "Reading sentences from file      : %s ...\n\n" % (settings.opts.inFile) )
    for sent in inF:
        sent = sent.strip()
        if settings.opts.force_decode: refsLst = getReferences(sent_indx)
        if settings.opts.skip_sents is not None and sent_indx < settings.opts.skip_sents:
            sent_indx += 1
            sent_count += 1
            continue

        parse_begin = time.time()
        lattice_obj = Lattice(sent_count, sent, relaxed_decoding)
        sys.stderr.write( "%3d Translating  :: %s\n" % (sent_count, sent) )
        dec_status = decode_CP(sent_count, lattice_obj)
        parse_time = time.time() - parse_begin

        tot_time += parse_time
        sys.stderr.write( "Translation time :: %1.3g sec\n\n" % (parse_time) )
        sent_count += 1
        sent_indx += 1
        if settings.opts.force_decode: coverage_cnt += dec_status
	Lattice.clear()

    inF.close()
    sys.stderr.write( "Time taken for decoding the set      : %1.3g sec\n\n" % (tot_time) )
    if settings.opts.force_decode:
        sys.stderr.write( "Number of sentences covered      : %d\n" % (coverage_cnt) )
        sys.stderr.write( "%% of sentences covered           : %g\n" % (float(coverage_cnt) * 100/ float(sent_indx)) )

def getReferences(sent_indx):
    '''Get the references in an array for force decoding'''

    global refFiles
    refsLst = []
    refHLst = [ open(file, 'r') for file in refFiles ]
    for refH in refHLst:
        indx = 0
        for sent in refH:
            if indx == sent_indx:
                sent = sent.strip()
                refsLst.append(sent)
                break
            indx += 1
        refH.close()

    del refHLst[:]
    return refsLst

def getRefFiles():
    '''Get the reference files for forced decoding'''

    global refFiles
    refFiles = []
    if os.path.exists(settings.opts.refFile): refFiles.append(settings.opts.refFile)
    else:
        i = 0
        ref_i = settings.opts.refFile + str(i)
        while os.path.exists(ref_i):
            refFiles.append(ref_i)
            i += 1
            ref_i = settings.opts.refFile + str(i)

    if not refFiles:
        sys.stderr.write("ERROR: Forced decoding requires at least one reference file.\n")
        sys.stderr.write("       But, the specified reference file doesn't exist or isn't a valid prefix. Exiting!!\n\n")
        sys.exit(1)

def consolidateRules(cntsFile):

    sys.stderr.write( "Consolidating rules from file : %s ...\n" % (cntsFile) )
    rulesUsedDict = {}
    rC = open(cntsFile, 'r')
    try:
        for line in rC:
            (src, tgt, cnts) = line.split(" ||| ")
            rule = src + " ||| " + tgt
            if ( rulesUsedDict.has_key(rule) ): rulesUsedDict[rule] += int(cnts)
            else: rulesUsedDict[rule] = int(cnts)
    finally:
        rC.close()

    tot_used_rules = len(rulesUsedDict.keys())
    tot_PT_rules = PhraseTable.getTotalRules()
    sys.stderr.write( "Total SCFG rules found for the set           : %g\n" % (tot_PT_rules) )
    sys.stderr.write( "# of unique rules used in N-best derivations : %g\n" % (tot_used_rules) )
    sys.stderr.write( "%% of rules used in the N-best list           : %g\n" % ((float(tot_used_rules) * 100.0) / float(tot_PT_rules)) )
    wC = open(cntsFile, 'w')
    for rule, r_cnt in sorted(rulesUsedDict.iteritems(), key=operator.itemgetter(1)):
        wC.write( "%s ||| %d\n" % (rule, r_cnt) )
    wC.close()

def main():

    global refFiles
    sent_count = settings.opts.sentindex * settings.opts.sent_per_file

    sys.stderr.write( "Loading LM file %s ... \n" % (settings.opts.lmFile) )
    t_beg = time.time()
    if (not settings.opts.no_lm_score) and settings.opts.use_srilm: lm_obj = SRILangModel(settings.opts.n_gram_size, settings.opts.lmFile, settings.opts.elider)
    elif not settings.opts.no_lm_score: lm_obj = KENLangModel(settings.opts.n_gram_size, settings.opts.lmFile, settings.opts.elider)
    t_end = time.time()
    sys.stderr.write( "Time taken for loading LM        : %1.3f sec\n\n" % (t_end - t_beg) )

    if settings.opts.force_decode:
        getRefFiles()
        RefPhrases(sent_count, refFiles)
    #PhraseTable()
    TOT_TERMS = 0  ###TODO: change it to a parameter in settings
    in_Fp = open(settings.opts.inFile, 'r')
    for line in in_Fp:
        TOT_TERMS = max(len(line.strip().split()), TOT_TERMS)
    in_Fp.close()

    PhraseTable(TOT_TERMS)

    readNParse(sent_count)                      # Parse the sentences

    lm_obj = ''                                 # Calls the __del__ in {SRI/KEN}LangModel to free the LM variable

    #if settings.opts.trace_rules > 0:
    #    consolidateRules(settings.opts.outFile+".trace")

if __name__ == "__main__":

    settings.args()         # Set the different default parameters
    main()
