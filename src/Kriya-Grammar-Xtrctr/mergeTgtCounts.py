## Consolidates the target sides of all rules along eith their counts ## 

import os
import sys
import heapq
from collections import defaultdict

def readNMerge(fileLst, outFile):
    '''Read entries from the individual files and merge counts on the fly'''

    candLst = []
    tgtDict = {}

    total_rules = 0
    stop_iteration = False
    fileTrackLst = [ 1 for file in fileLst ]

    print "Reading target side rules and consolidating their counts ..."
    fHLst = [ open(file, 'r') for file in fileLst ]
    oF = open(outFile, 'w')
    while True:
        if stop_iteration:
            break

        for indx, f_track in enumerate( fileTrackLst ):
            if f_track == 0 or f_track == 9:
                continue

            fileTrackLst[indx] = 0
            line = fHLst[indx].readline()
            line = line.strip()
            if line == '':
                fileTrackLst[indx] = 9          # Set 9 if 'EOF' is reached
                stop_iteration = True
                continue

            stop_iteration = False
            (tgt, r_count) = line.split(' ||| ')
            r_count = float( r_count )

            if tgtDict.has_key(tgt):
                valTup = (tgtDict[tgt][0] + r_count, tgtDict[tgt][1] + [indx])
                tgtDict[tgt] = valTup
            else:
                tgtDict[tgt] = (r_count, [indx])
                heapq.heappush(candLst, tgt)

        if len(candLst) == 0: continue
        popped_tgt = heapq.heappop(candLst)
        (r_count, indxLst) = tgtDict.pop(popped_tgt)
        oF.write( "%s ||| %g\n" % (popped_tgt, r_count) )
        total_rules += 1
        for indx1 in indxLst:
            fileTrackLst[indx1] = 1
            stop_iteration = False

    for fH in fHLst:
        fH.close()
    oF.close()
    print( "Total # of rules : %d" % (total_rules) )

def main():
    tgtPath = sys.argv[1]
    fileLst=[]
    for f in os.listdir(tgtPath):
        full=os.path.join(tgtPath, f)
        if os.path.isfile(full) and f.startswith('tgt.'):
            fileLst.append(full)

    # merge the target counts from the files in the fileLst
    consTgtFile = os.path.join(tgtPath, "tgt_rules.all.out")
    readNMerge(fileLst, consTgtFile)

if __name__ == '__main__':
    main()

