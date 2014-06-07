import sys
from itertools import izip


indx = 0
prev_sent_id = -1

ref_files_str = sys.argv[1]
nBestFile = sys.argv[2]
outrefFile = sys.argv[3]
outHypFile = sys.argv[4]
if len(sys.argv) == 6:
    set_id = sys.argv[5]
else:
    set_id = 'Kriya-PRO'

refH = []
refLines = []
for refFile in ref_files_str.split(':'):
    refH.append( open(refFile, 'r') )

wrF = open(outrefFile, 'w')
whF = open(outHypFile, 'w')

with open(nBestFile, 'r') as hF:
    for line2 in hF:
        line2 = line2.strip()
        (sent_id, sent, _) = line2.split('|||', 2)
        sent_id = int(sent_id)
        sent = sent.strip()
        whF.write("%s  (%s.%d)\n" % (sent, set_id, indx))

        if (sent_id > prev_sent_id):
            del refLines[:]
            for rF in refH:
                line1 = rF.readline()
                refLines.append( line1.strip() )
        for line1 in refLines:
            wrF.write("%s  (%s.%d)\n" % (line1, set_id, indx))
        indx += 1
        prev_sent_id = sent_id

for rF in refH:
    rF.close()
hF.close()
wrF.close()
whF.close()

