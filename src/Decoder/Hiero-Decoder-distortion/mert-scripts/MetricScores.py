import os
import os.path
import subprocess
import sys

class MetricScores(object):

    __slots__ = "hypBLEUFile", "refBLEUFile", "hypTERFile", "refTERFile"

    def __init__(self, workDir, ref_stem, nbest_file, bestHypIndxLst, logFile):
        metricsDir = workDir + "Metrics-stats/"
        self.hypBLEUFile = metricsDir + "hyp.bleu.out"
        self.hypTERFile = metricsDir + "hyp.ter.out"
        self.refTERFile = metricsDir + "ref.ter.out"
        self.refBLEUFile = ref_stem

        if not os.path.isfile(self.refTERFile):
            self.createTERRefFile()

        self.getBestHyps(bestHypIndxLst, nbest_file)
        self.computeBLEU(logFile)
        self.computeRIBES(logFile)
        self.computeTER(metricsDir, logFile)

    def createTERRefFile(self):
        refFilesLst = []
        if os.path.exists(self.refBLEUFile): refFilesLst.append(self.refBLEUFile)
        else:
            indx = 0
            while True:
                ref_file = self.refBLEUFile + str(indx)
                if os.path.exists(ref_file): refFilesLst.append(ref_file)
                else: break
                indx += 1
        rFL = [open(ref_file, 'r') for ref_file in refFilesLst]
        rTF = open(self.refTERFile, 'w')
        indx = 0
        for line in rFL[0]:
            line = line.strip()
            rTF.write( "%s  (Kriya-PRO.%d)\n" % (line, indx) )
            for rF in rFL[1:]:
                for line1 in rF:
                    line1 = line1.strip()
                    rTF.write( "%s  (Kriya-PRO.%d)\n" % (line1, indx) )
                    break
            indx += 1
        for rF in rFL: rF.close()
        rTF.close()

    def getBestHyps(self, bestHypIndxLst, nbest_file):
        h_ind = 0
        bestHyps = []
        ref_indx_prev = 0
        nbF = open(nbest_file, 'r')
        for line in nbF:
            hypItem = line.rsplit("|||")
            ref_indx = int(hypItem[0])
            if ref_indx == ref_indx_prev + 1:
                h_ind = 0
            if bestHypIndxLst[ref_indx] == h_ind:
                hyp = hypItem[1].strip()
                bestHyps.append(hyp)

            ref_indx_prev = ref_indx
            h_ind = h_ind +1

        nbF.close()
        self.writeHyps(bestHyps)

    def writeHyps(self, bestHyps):
        oBF = open(self.hypBLEUFile, "w")
        oTF = open(self.hypTERFile, "w")
        indx = 0
        for hyp in bestHyps:
            oBF.write( "%s\n" % (hyp) )
            oTF.write( "%s  (Kriya-PRO.%d)\n" % (hyp, indx) )
            indx += 1
        oBF.close()
        oTF.close()

    def computeBLEU(self, logFile):
        mertDir = sys.path[0]
        iF = open(self.hypBLEUFile, 'r')
        oF = open(logFile, 'w')

        cmdArgs = ["perl", mertDir + "/multi-bleu.perl", self.refBLEUFile]
        print "Executing command    : ", ' '.join( cmdArgs )
        subprocess.check_call(cmdArgs, stdin=iF, stdout=oF)
        iF.close()
        oF.close()

    def computeRIBES(self, logFile):
        mertDir = sys.path[0]
        oF = open(logFile, 'a')

        py3_home = os.environ.get("PY3_HOME")
        cmdArgs = [py3_home + "/bin/python3", mertDir + "/RIBES.py"]
        if os.path.exists(self.refBLEUFile) and os.path.isfile(self.refBLEUFile):
            cmdArgs += ["-r", self.refBLEUFile]
        else:
            ref_id = 0
            while True:
                ref_file = self.refBLEUFile + str(ref_id)
                if os.path.exists(ref_file) and os.path.isfile(ref_file):
                    cmdArgs += ["-r", ref_file]
                else: break
                ref_id += 1
        cmdArgs += [self.hypBLEUFile]
        print "Executing command    : ", ' '.join( cmdArgs )
        subprocess.check_call(cmdArgs, stdout=oF)
        oF.close()

    def computeTER(self, metricsDir, logFile):
        terJarFile = os.environ.get("TER_JAR")
        if ( terJarFile is None ):
            sys.stderr.write("Error: Environment variable TER_JAR is not set. Exiting!!\n")
            sys.exit(1)
        ter_pre = metricsDir + "final.ter"
        terLogFile = metricsDir + "final.tercom.log"

        lF = open(terLogFile, 'w')
        ter_scr = os.path.abspath( os.path.dirname(sys.argv[0]) )
        if ter_scr.endswith('/'): ter_scr = ter_scr + 'run_ter.sh'
        else: ter_scr = ter_scr + '/run_ter.sh'
        cmdArgs = ['sh', ter_scr, terJarFile, self.refTERFile, self.hypTERFile, ter_pre]
        print "Executing command    : ", ' '.join( cmdArgs )
        subprocess.check_call(cmdArgs, stdout=lF)
        lF.close()

        oF = open(logFile, 'a')
        cmdArgs = ["grep", "Total", terLogFile]
        print "Executing command    : ", ' '.join( cmdArgs )
        subprocess.check_call(cmdArgs, stdout=oF)
        oF.close()

