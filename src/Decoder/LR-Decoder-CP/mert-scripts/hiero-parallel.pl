#! /usr/bin/perl

# $Id: moses-parallel.pl 1598 2008-04-23 10:03:45Z nicolabertoldi $
#######################
# Revision history
#
# 01 May 2009 modified for hiero by Baskaran Sankaran
# 02 Aug 2006 added strict requirement
# 01 Aug 2006 fix bug about inputfile parameter
#             fix bug about suffix index generation
# 31 Jul 2006 added parameter for reading queue parameters
# 29 Jul 2006 added code to handling consfusion networks
# 28 Jul 2006 added a better policy for removing jobs from the queue in case of killing signal (CTRL-C)
#             added the parameter -qsub-prefix which sets the prefix for the name of submitted jobs
# 27 Jul 2006 added safesystem() function and other checks to handle with process failure
#             added checks for existence of decoder and configuration file
# 26 Jul 2006 fix a bug related to the use of absolute path for srcfile and nbestfile

use strict;

#######################
#Customizable parameters 

#parameters for submiiting processes through Sun GridEngine
my $queueparameters="-l mem=5gb -l walltime=01:30:00";

# look for the correct pwdcmd 
my $pwdcmd = getPwdCmd();

my $workingdir = `$pwdcmd`; chomp $workingdir;
my $tmpdir="$workingdir/tmp$$";
my $splitpfx="split$$";

$SIG{'INT'} = \&kill_all_and_quit; # catch exception for CTRL-C

#######################
#Default parameters 
my $jobscript="$workingdir/job$$";
my $qsubout="$workingdir/out.job$$";
my $qsuberr="$workingdir/err.job$$";


my $mosesparameters="";
my $feed_moses_via_stdin = 0;
      # a workaround, for a reason, the default "-input-file X" blocks
      # my moses, while "< X" works fine.
my $cfgfile=""; #configuration file

my $version=undef;
my $help=0;
my $dbg=0;
my $jobs=4;
my $mosescmd="$ENV{MOSESBIN}/moses"; #decoder in use
my $decoder_prefix=undef;
my $kriya_opts="";
my $inputdir=undef;
my $outputdir=undef;
my $ruledir=undef;
my $ttable = undef;
my $lm_file=undef;
my @nbestlist=();
my $nbestlist=undef;
my $nbestfile=undef;
my $oldnbestfile=undef;
my $oldnbest=undef;
my $nbestflag=0;
my @wordgraphlist=();
my $wordgraphlist=undef;
my $wordgraphfile=undef;
my $wordgraphflag=0;
my $robust=1; # undef; # resubmit crashed jobs
my $mert_status= 100;  # Three digit code to indicate the current state of the 'mert' and has the structure:
                       # <Iteration no, decoding status, concatenation of nbest status>; default: 100
                       # iteration is 1 or above, status digit 0 means not begun, 1 means partly completed
my $prev_jobid;        # Used to specify the job-id when mert was aborted
my $logfile="";
my $logflag="";
my $searchgraphlist="";
my $searchgraphfile="";
my $searchgraphflag=0;
my $qsubname="MOSES";
my $nodes_prop="";
my $old_sge = 0; # assume old Sun Grid Engine (<6.0) where qsub does not
                 # implement -sync and -b

#######################
# Command line options processing
sub init(){
    use Getopt::Long qw(:config pass_through no_ignore_case permute);
    GetOptions('version'=>\$version,
	       'help'=>\$help,
	       'debug'=>\$dbg,
	       'jobs=i'=>\$jobs,
	       'decoder=s'=> \$mosescmd,
	       'decoder-prefix=s'=>\$decoder_prefix,
           'kriya-options=s'=>\$kriya_opts,
	       'robust' => \$robust,
	       'mert-status=i' => \$mert_status,
	       'prev-jobid=i' => \$prev_jobid,
	       'decoder-parameters=s'=> \$mosesparameters,
	       'feed-decoder-via-stdin'=> \$feed_moses_via_stdin,
	       'logfile=s'=> \$logfile,
	       'i|inputdir|input-dir=s'=> \$inputdir,
	       'output-dir=s' => \$outputdir,
	       'rule-dir=s' => \$ruledir,
	       'ttable-file=s' => \$ttable,
	       'lmfile=s' => \$lm_file,
	       'n-best-list=s'=> \$nbestlist,
	       'n-best-file=s'=> \$oldnbestfile,
	       'n-best-size=i'=> \$oldnbest,
	       'output-search-graph|osg=s'=> \$searchgraphlist,
	       'output-word-graph|owg=s'=> \$wordgraphlist,
	       'qsub-prefix=s'=> \$qsubname,
	       'nodes-prop=s' => \$nodes_prop,
	       'queue-parameters=s'=> \$queueparameters,
	       'config|f=s'=>\$cfgfile,
	       'old-sge' => \$old_sge,
	       ) or exit(1);

    getNbestParameters();
    getLogParameters();

#    print_parameters();
#    print STDERR "nbestflag:$nbestflag\n";
#    print STDERR "inputdir:$inputdir\n";
}


#######################
##print version
sub version(){
#    print STDERR "version 1.0 (15-07-2006)\n";
#    print STDERR "version 1.1 (17-07-2006)\n";
#    print STDERR "version 1.2 (18-07-2006)\n";
#    print STDERR "version 1.3 (21-07-2006)\n";
#    print STDERR "version 1.4 (26-07-2006)\n";
#    print STDERR "version 1.5 (27-07-2006)\n";
#    print STDERR "version 1.6 (28-07-2006)\n";
#    print STDERR "version 1.7 (29-07-2006)\n";
#    print STDERR "version 1.8 (31-07-2006)\n";
#    print STDERR "version 1.9 (01-08-2006)\n";
#    print STDERR "version 1.10 (02-08-2006)\n";
#    print STDERR "version 1.11 (10-10-2006)\n";
#    print STDERR "version 1.12 (27-12-2006)\n";
    print STDERR "version 1.13 (29-12-2006)\n";
    exit(1);
}

#usage
sub usage(){
    print STDERR "moses-parallel.pl [parallel-options]  [moses-options]\n";
    print STDERR "Options marked (*) are required.\n";
    print STDERR "Parallel options:\n";
    print STDERR "*  -decoder <file> Moses decoder to use\n";
    print STDERR "*  -decoder-prefix <prefix>   prefix used for executing decoder (any interpretor etc.)";
    print STDERR "*  -kriya-options <options to kriya>  options directly passed to Kriya (non-feature weight options)\n";
    print STDERR "*  -i|inputdir|input-dir <dir>   directory having the input files to translate\n";
    print STDERR "*  -output-dir <dir> directory for writing the output files\n";
    print STDERR "*  -rule-dir <dir>   directory having the SCFG rule files corresponding to the input files\n";
    print STDERR "*  -lmfile <file>   LM file to be used for decoding";
    print STDERR "*  -jobs <N> number of required jobs\n";
    print STDERR "   -logfile <file> file where storing log files of all jobs\n";
    print STDERR "   -qsub-prefix <string> name for sumbitte jobs\n";
    print STDERR "   -queue-parameters <string> specific requirements for queue\n";
    print STDERR "   -old-sge Assume Sun Grid Engine < 6.0\n";
    print STDERR "   -debug debug\n";
    print STDERR "   -version print version of the script\n";
    print STDERR "   -help this help\n";
    print STDERR "Moses options:\n";
    print STDERR "   -output-search-graph (osg) <file>: Output connected hypotheses of search into specified filename\n";
    print STDERR "   -output-word-graph (osg) '<file> <0|1>': Output stack info as word graph. Takes filename, 0=only hypos in stack, 1=stack + nbest hypos\n";
    print STDERR "   IMPORTANT NOTE: use single quote to group parameters of -output-word-graph\n";
    print STDERR "                   This is different from standard moses\n";
    print STDERR "   -n-best-list '<file> <N> [distinct]' where\n";
    print STDERR "                <file>:   file where storing nbest lists\n";
    print STDERR "                <N>:      size of nbest lists\n";
    print STDERR "                distinct: (optional) to activate generation of distinct nbest alternatives\n";
    print STDERR "   IMPORTANT NOTE: use single quote to group parameters of -n-best-list\n";
    print STDERR "                   This is different from standard moses\n";
    print STDERR "   IMPORTANT NOTE: The following two parameters are now OBSOLETE, and they are no more supported\n";
    print STDERR "                   -n-best-file <file> file where storing nbet lists\n";
    print STDERR "                   -n-best-size <N> size of nbest lists\n";
    print STDERR "    NOTE: -n-best-file-n-best-size    are passed to the decoder as \"-n-best-list <file> <N>\"\n";
    print STDERR "*  -config (f) <cfgfile> configuration file\n";
    print STDERR "   -decoder-parameters <string> specific parameters for the decoder\n";
    print STDERR "All other options are passed to Moses\n";
    print STDERR "  (This way to pass parameters is maintained for back compatibility\n";
    print STDERR "   but preferably use -decoder-parameters)\n";
    exit(1);
}

#printparameters
sub print_parameters(){
    print STDERR "Input directory: $inputdir\n";
    print STDERR "Rule directory: $ruledir\n" if (defined $ruledir);
    print STDERR "T-table file: $ttable\n" if (defined $ttable);
    print STDERR "Output directory: $outputdir\n";
    print STDERR "LM file: $lm_file\n";
    print STDERR "Configuration file: $cfgfile\n";
    print STDERR "Decoder in use: $mosescmd\n";
    print STDERR "Decoder prefix: $decoder_prefix\n";
    print STDERR "Other Kriya options: $kriya_opts\n";
    print STDERR "Number of jobs:$jobs\n";
    print STDERR "Nbest list: $nbestlist\n" if ($nbestflag);
    print STDERR "Output Search Graph: $searchgraphlist\n" if ($searchgraphflag);
    print STDERR "Output Word Graph: $wordgraphlist\n" if ($wordgraphflag);
    print STDERR "LogFile:$logfile\n" if ($logflag);
    print STDERR "Qsub name: $qsubname\n";
    print STDERR "Queue parameters: $queueparameters\n";

    print STDERR "parameters directly passed to Moses: $mosesparameters\n";
}

#get parameters for log file
sub getLogParameters(){
    if ($logfile){ $logflag=1; }
}

#get parameters for nbest computation (possibly from configuration file)
sub getNbestParameters(){
    if (!$nbestlist){
	open (CFG, "$cfgfile");
	while (chomp($_=<CFG>)){
	    if (/^\[n-best-list\]/){
		my $tmp;
		while (chomp($tmp=<CFG>)){
		    last if $tmp eq "" || $tmp=~/^\[/;
		    $nbestlist .= "$tmp ";
		}
		last;
	    }
	}
	close(CFG);
    }

    if ($nbestlist){
	if ($oldnbestfile){
	    print STDERR "There is a conflict between NEW parameter -n-best-list and OBSOLETE parameter -n-best-file\n";
	    print STDERR "Please use only -nbest-list '<file> <N> [distinct]\n";
	    exit;
	}
    }
    else{
	if ($oldnbestfile){
	    print STDERR "You are using the OBSOLETE parameter -n-best-file\n";
	    print STDERR "Next time please use only -n-best-list '<file> <N> [distinct]\n";
	    $nbestlist="$oldnbestfile";
	    if ($oldnbest){ $nbestlist.=" $oldnbest"; }
	    else { $nbestlist.=" 1"; }
	}
    }

    if ($nbestlist){
	my @tmp=split(/[ \t]+/,$nbestlist);
	@nbestlist = @tmp;

	if ($nbestlist[0] eq '-'){ $nbestfile="nbest"; }
	else{ chomp($nbestfile=`basename $nbestlist[0]`);     }
	$nbestflag=1;
    }
}

#######################
#Script starts here

init();

version() if $version;
usage() if $help;

if ($mert_status =~ /^\d+?11$|^\d+?12$/) {
    print STDERR "N-best file : $nbestlist\n";
    if (-e "${nbestlist}.gz") { safesystem("gunzip ${nbestlist}.gz") or die; }
    if (-e $nbestlist) {
        print  STDERR "INFO: MERT Status: $mert_status. Decoding for this iteration seem to be completed. Found the merged N-best list as well.!!\n";
        exit(0);
    }
    print  STDERR "ERROR: MERT Status: $mert_status. However the N-best list could not be found. Exiting!!\n";
    exit(1);
}

if ($mert_status != 100 && !defined $prev_jobid) {
    print STDERR "ERROR: Iteration specified as ($mert_status)\n";
    print STDERR "Error: To continue this iteration please specify the id for the previous job. Exiting!!\n";
    exit(1);
}

if (!defined $inputdir || !defined $mosescmd || ! defined $cfgfile) {
    print STDERR "Please specify -input-dir, -decoder and -config\n";
    usage();
}

#checking if inputdir exists
if (! -e ${inputdir} ){
    print STDERR "Input directory ($inputdir) does not exists\n";
    usage();
}

#checking if decoder exists
if (! -e $mosescmd) {
    print STDERR "Decoder ($mosescmd) does not exists\n";
    usage();
}

#checking if configfile exists
if (! -e $cfgfile) {
    print STDERR "Configuration file ($cfgfile) does not exists\n";
    usage();
}

if (defined $decoder_prefix) { $decoder_prefix =~ s/\=/ /; }
$queueparameters =~ s/__/ /;
$nodes_prop =~ s/__/ /;

if ($dbg) { 
    print_parameters();  # debug mode: just print and do not run
    exit(1);
}


my $cmd;
my $sentenceN;
my $splitN;
my $___SENT_PER_RUN = 100;
my $in_file;
my $rule_file;
my $out_file;
my $status_file;

my $iteration;
my $decode_incomplete;
my $cat_incomplete;

my @tmplist = ();
my @idxlist = ();
my @idx_todo = ();
my @sgepids =();
my @idx_status = ();
my @idx_submitted = ();

chomp(@tmplist=`ls $inputdir/*.out`);
grep(s/^$inputdir\/(\d+)\.out$/$1/e,@tmplist);
@tmplist = sort {$a <=> $b} @tmplist;
@idxlist = @tmplist[0..$jobs-1];

$mert_status =~ m/^(\d+)?(\d)(\d)$/;
$iteration = $1;
$decode_incomplete = $2;
$cat_incomplete = $3;

$cfgfile =~ /run(\d+)\./;
if ($iteration != $1) {
    print STDERR "WARNING: Mert status variable ($mert_status) and the interation number in the config file ($cfgfile) are not the same.\n";
    print STDERR "         Using the iteration information from Mert-status variables.\n";
    $cfgfile =~ s/(run)\d+(\.)/$1$iteration$2/;
}
$mosesparameters.="@ARGV --config $cfgfile";

if (!$cat_incomplete) {
    if (!$decode_incomplete) {
	@idx_todo = @idxlist;
	safesystem("mkdir -p $tmpdir") or die;
	$status_file = $tmpdir."/mert_status.out";
	preparing_script();
    }
    else {
	my %tmphash = ();
	grep(s/^(\d+)$/$tmphash{$1}=1;$1/e,@tmplist);
	$tmpdir = "$workingdir/tmp$prev_jobid";
	$jobscript="$workingdir/job$prev_jobid";
	$qsubout="$workingdir/out.job$prev_jobid";
	$qsuberr="$workingdir/err.job$prev_jobid";

	$status_file = $tmpdir."/mert_status.out";
	open(MS, $status_file) or die "Can't read file MERT status file: ($status_file)";
	while(<MS>) {
	    chomp;
	    next if(length() == 0);
	    if (exists $tmphash{$_}) { delete $tmphash{$_}; }
	    else { die "Mismatch in the MERT status file ($status_file) entries & files in input directory ($inputdir): $_\n"; }
	}
	close(MS);
	foreach (keys %tmphash) {
	    push @idx_todo,$_;
	    if (-e "$qsubout$_") { safesystem("rm $qsubout$_") or kill_all_and_quit(); }
	}
    }
    submit_jobs();
}
else {
    $tmpdir = "$workingdir/tmp$prev_jobid";
    $jobscript="$workingdir/job$prev_jobid";
    $qsubout="$workingdir/out.job$prev_jobid";
    $qsuberr="$workingdir/err.job$prev_jobid";

    print STDERR "*** $tmpdir\n";
    print STDERR "*** $jobscript\n";
    print STDERR "*** $qsubout\n";
    print STDERR "*** $qsuberr\n";
}
merge_nbest();              # Concatenate the nbest files


# launching process through the queue and if robust switch is used, redo jobs that crashed
sub submit_jobs() {

    my $looped_once = 0;
    my $job_cnt = 0;
    while((!$robust && !$looped_once) || ($robust && scalar @idx_todo)) {
	  $looped_once = 1;
	  my $idx = shift(@idx_todo);
	  $job_cnt++;
	  print STDERR "Job# $job_cnt >> ";
      # Without node properties
	  #$cmd="qsub $queueparameters -o $qsubout$idx -e $qsuberr$idx -N $qsubname$idx ${jobscript}${idx}.sh >& ${jobscript}${idx}.log";
      # With node properties
	  $cmd="qsub $nodes_prop $queueparameters -o $qsubout$idx -e $qsuberr$idx -N $qsubname$idx ${jobscript}${idx}.sh >& ${jobscript}${idx}.log";
	  print STDERR "$cmd\n" if $dbg;
	  safesystem($cmd) or die;

	  my ($res,$id);
	  open (IN,"${jobscript}${idx}.log") or die "Can't read id of job ${jobscript}${idx}.log";

	  #foreach $res (<INFO>)  {   
           # chomp($res);    
	  #  split(/\./,$res);
	  #  $id=$_[0];
          #}

	  chomp($res=<IN>);
	  split(/\./,$res);
	  $id=$_[0];
	  close(IN);

	  push @sgepids, $id;
	  push @idx_status,99;
	  push @idx_submitted,$idx;

	  if(($job_cnt % 160) == 0 || scalar(@idx_todo) == 0) {
	    wait_for_completion(join(":", @sgepids));
	    @sgepids = ();
	    @idx_status = ();
	    @idx_submitted = ();
	  }
	  last if !scalar(@idx_todo);          # exit the loop if all the jobs are done
      sleep(1);
    }
}


#concatenating translations and removing temporary files
sub merge_nbest() {
#    concatenate_1best();
    concatenate_logs() if $logflag;
    concatenate_nbest() if $nbestflag;  
    safesystem("cat nbest$$ >> /dev/stdout") if $nbestlist[0] eq '-';
    remove_temporary_files();
}


sub wait_for_completion() {
    my $hj = shift;    #waiting until all these jobs have finished

    # use the -W depend=afterok option for qsub
    my $syncscript = "mert.W.sh";
    safesystem("echo '/bin/ls' > $syncscript") or kill_all_and_quit();
    $cmd="qsub -l mem=200m -l walltime=00:03:00 -W depend=afterok:$hj -j oe -o $qsubname.W.err -e $qsubname.W.err -N $qsubname.W $syncscript >& $qsubname.W.log";
    safesystem($cmd) or kill_all_and_quit();

    my $failure = 1;
    print STDERR "Waiting for jobs to complete: checking exit status ...\n";
    while ($failure) {
        $failure=&check_exit_status();
        last if !$failure;
        sleep(30);
    }
    sleep(60);  # Extra wait for possibly unfinished processes

    kill_all_and_quit() if $failure && !$robust;

    # check if some translations failed
    my @idx_still_todo = ();
    @idx_still_todo = check_translation();
    if ($robust) {
	my $element;
	my $found_element;
	# if robust, redo crashed jobs
	if ((scalar @idx_still_todo) == (scalar @idxlist)) {
	    # ... but not if all crashed
	    print STDERR "everything crashed, not trying to resubmit jobs\n";
	    kill_all_and_quit();
	}
	foreach $element (@idx_still_todo) {
	    $found_element = 0;
	    if (grep {$_ eq $element} @idx_todo) {
		$found_element = 1;
		next;
	    }
	    if (!$found_element) {
		push @idx_todo,$element;
		if (-e "$qsubout$element") { safesystem("rm $qsubout$element") or kill_all_and_quit(); }
	    }
	}
    }
    else {
	if (scalar (@idx_still_todo)) {
	    print STDERR "some jobs crashed: ".join(" ",@idx_still_todo)."\n";
	    kill_all_and_quit();
	}
    }
}


#script creation
sub preparing_script(){
    foreach my $idx (@idxlist){
	my $scriptheader="\#\! /bin/tcsh\n\n";
	$scriptheader.="uname -a\n\n";
	$scriptheader.="cd $workingdir\n\n";

	$in_file = $inputdir."/".$idx.".out";
	if (defined $ruledir) {
	    $rule_file = $ruledir."/".$idx.".out";
	}
	elsif (defined $ttable) {
	    $rule_file = $ttable;
	}
	$out_file = $tmpdir."/".$idx.".out";

	open (OUT, "> ${jobscript}${idx}.sh");
	print OUT $scriptheader;
    ##print OUT "source /hpc/software/etc/colony-login\n";
    ##print OUT "module load LANG/PYTHON/2.6.2\n\n";
    #print OUT "source /cs/natlang-sw/etc/natlang-login\n";
    #print OUT "module load NL/LANG/PYTHON/2.6.2\n\n";

	my $sent_indx = $idx - 1;
	## ********* ONLY FOR DEBUGGING ********* ##
	#print OUT "$decoder_prefix $mosescmd $out_file > $tmpdir/run_$idx.out\n\n";

	print OUT "$decoder_prefix $mosescmd $mosesparameters $kriya_opts --index $sent_indx --inputfile $in_file --outputfile $out_file --ttable-file $rule_file --lmodel-file $lm_file >& $tmpdir/run_$idx.out\n\n";
	print OUT "echo exit status \$\?\n\n";

 	##print OUT "module unload LANG/PYTHON/2.6.2\n\n";
	#print OUT "module unload NL/LANG/PYTHON/2.6.2\n\n";

    print OUT "rm -rf /local-scratch/\${PBS_JOBID}\n\n";

	print OUT "echo exit status \$\?\n\n";
	close(OUT);

	#setting permissions of each script
	chmod(oct(755),"${jobscript}${idx}.sh");
    }
}

sub concatenate_nbest(){
    my $oldcode="";
    my $newcode=-1;
    my %inplength = ();
    my $offset = 0;

    # get the list of feature and set a fictitious string with zero scores
    open (IN, "${nbestfile}.${splitpfx}$idxlist[0]");
    my $str = <IN>;
    chomp($str);
    close(IN);
    my ($code,$trans,$featurescores,$globalscore)=split(/\|\|\|/,$str);

    my $emptytrans = "  ";
    my $emptyglobalscore = " 0.0";
    my $emptyfeaturescores = $featurescores;
    $emptyfeaturescores =~ s/[-0-9\.]+/0/g;

    my $outnbest=$nbestlist[0];
    if ($nbestlist[0] eq '-'){ $outnbest="nbest$$"; }

#    open (OUT, "> $outnbest");
    foreach my $idx (@idxlist){
	$out_file = $tmpdir."/".$idx.".out";
	safesystem("cat $out_file >> $outnbest") or kill_all_and_quit();
=begin
        #computing the length of n-best list of each sentence
	chomp(@nbest_cnt=`cat ${out_file} | cut -d'|' -f1 | uniq -c`);
	foreach (@nbest_cnt) {
	    s/^\s+//;
	    s/(.+)?\s+(.+)?/$inplength{$2}=$1;/eg;
	}

	open (IN, $out_file);
	while (<IN>){
	    my ($code,@extra)=split(/\|\|\|/,$_);
	    $code += $offset;
	    if ($code ne $oldcode){
                # if there is a jump between two consecutive codes
                # it means that an input sentence is not translated
                # fill this hole with a "fictitious" list of translation
                # comprising just one "emtpy translation" with zero scores
		while ($code - $oldcode > 1){
		    $oldcode++;
		    print OUT join("\|\|\|",($oldcode,$emptytrans,$emptyfeaturescores,$emptyglobalscore)),"\n";
		}
	    }
	    $oldcode=$code;
	    print OUT join("\|\|\|",($oldcode,@extra));
	}
	close(IN);
	$offset += $inplength{$idx};

	while ($offset - $oldcode > 1){
	    $oldcode++;
	    print OUT join("\|\|\|",($oldcode,$emptytrans,$emptyfeaturescores,$emptyglobalscore)),"\n";
	}
=cut
    }
#    close(OUT);
}

sub concatenate_1best(){
    foreach my $idx (@idxlist){
	my @in=();
	open (IN, "${in_file}.${splitpfx}${idx}.trans");
	@in=<IN>;
	print STDOUT "@in";
	close(IN);
    }
}

sub concatenate_logs(){
    open (OUT, "> ${logfile}");
    foreach my $idx (@idxlist){
	my @in=();
	open (IN, "$qsubout$idx");
	@in=<IN>;
	print OUT "@in";
	close(IN);
    }
    close(OUT);
}

sub check_exit_status(){
    my $failure;
    my $idx;
    for(my $i=0; $i<@idx_submitted; $i++) {
        $idx = $idx_submitted[$i];
        $failure=99;                   # '99' indicates Unknown
        if($idx_status[$i] == 99) {
            if (-e "$qsubout$idx") {
                open(IN,"$qsubout$idx");
                while (<IN>) {
                    if (/exit status 0/) { $failure=0; last; }
                    else {
                        if (/exit status 1/ || /exit status 137/) {
                            push @idx_todo,$idx;
                            $failure=0;
                            last;
                        }
                    }
                }
                close(IN);
                unlink("$qsubout$idx");
                $idx_status[$i] = $failure;
                my $status = $failure==99 ? 'Unknown' : $failure;
                print STDERR "check_exit_status of job $idx : $status\n";
            }
        }
    }

    my $overall_status = 0;
    foreach (@idx_status) {
        if ($_ > 0) {
            $overall_status = 1;
            last;
        }
    }
    return $overall_status;
}

sub kill_all_and_quit(){
    print STDERR "Got interrupt or something failed.\n";
    print STDERR "kill_all_and_quit\n";
    foreach my $id (@sgepids){
	print STDERR "canceljob $id\n";
	safesystem("canceljob $id");
    }
    print STDERR "Translation was not performed correctly\n";
    print STDERR "or some of the submitted jobs died.\n";
    print STDERR "canceljob function was called for all submitted jobs\n";

    exit(1);
}

sub check_translation(){
    #checking if all sentences were translated
    my $inputN;
    my $outputN;
    my @failed = ();
    $status_file = $tmpdir."/mert_status.out";
    open(MS, ">>$status_file") or die "Can't read file MERT status file: ($status_file)";
    foreach my $idx (@idx_submitted){
	$in_file = $inputdir."/".$idx.".out";
	$out_file = $tmpdir."/".$idx.".out";
	if (!-e "$out_file") { push @failed,$idx; next; }

	chomp($inputN=`wc -l ${in_file} | cut -d' ' -f1`);
	chomp($outputN=`cat ${out_file} | cut -d'|' -f1 | uniq | wc -l`);
	if ($inputN != $outputN){
	    print STDERR "Split ($idx) were not entirely translated\n";
	    print STDERR "outputN=$outputN inputN=$inputN\n";
	    print STDERR "outputfile=${out_file} inputfile=${in_file}\n";
	    push @failed,$idx;
	    safesystem("rm $out_file") or kill_all_and_quit();   # Remove the incomplete file of the failed job
	}
	else {              # record the info that job $idx is completed in $status_file
	    print MS "$idx\n";
	}
    }
    close(MS);
    return @failed;
}

sub remove_temporary_files(){
    #removing temporary files
    foreach my $idx (@idxlist){
	$out_file = $tmpdir."/".$idx.".out";
	unlink("${out_file}");
	$out_file = $tmpdir."/run_$idx.out";
	unlink("$tmpdir/run_$idx.out");
	if ($nbestflag){ unlink("${nbestfile}.${splitpfx}${idx}"); }
	unlink("${jobscript}${idx}.sh");
	unlink("${jobscript}${idx}.log");
	unlink("$qsubname.W.sh");
	unlink("$qsubname.W.log");
	unlink("$qsubname.W.err");
	unlink("$qsubout$idx");
	unlink("$qsuberr$idx");
	rmdir("$tmpdir");
    }
    $status_file = $tmpdir."/mert_status.out";
    if (-e $status_file) { unlink("$status_file"); }
    if ($nbestflag && $nbestlist[0] eq '-'){ unlink("${nbestfile}$$"); };
}

sub safesystem {
    print STDERR "Executing: @_\n";
    system(@_);
    if ($? == -1) {
	print STDERR "Failed to execute: @_\n  $!\n";
	exit(1);
    }
    elsif ($? & 127) {
	printf STDERR "Execution of: @_\n  died with signal %d, %s coredump\n",
	($? & 127),  ($? & 128) ? 'with' : 'without';
	exit 1;
    }
    else {
	my $exitcode = $? >> 8;
	print STDERR "Exit code: $exitcode\n" if $exitcode;
	return ! $exitcode;
    }
}

# look for the correct pwdcmd (pwd by default, pawd if it exists)
# I assume that pwd always exists
sub getPwdCmd(){
    my $pwdcmd="pwd";
    my $a;
    chomp($a=`which pawd | head -1 | awk '{print $1}'`);
    if ($a && -e $a){	$pwdcmd=$a;	}
    return $pwdcmd;
}
