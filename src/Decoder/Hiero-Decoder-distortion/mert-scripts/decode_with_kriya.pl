#! /usr/bin/perl

# decode_with_kriya.pl #
# 29-12-2010 #

use File::Basename;
use strict;
use warnings;

###################
# Cluster parameters 

# qsub parameters for HPC
my $qsub_params="-l mem=5gb -l walltime=01:30:00";

# look for the correct pwdcmd 
my $pwdcmd = getPwdCmd();

my $workingdir = `$pwdcmd`; chomp $workingdir;
my $tmpdir="$workingdir/tmp$$";
my $splitpfx="split$$";

$SIG{'INT'} = \&kill_all_and_quit; # catch manual interrupt

# Get MERT run-id
my $run = get_mert_runid();

my $version=undef;
my $help=0;
my $dbg=0;

###################
# Default parameters 
my $jobscript="$workingdir/job$$";
my $qsubout="$workingdir/out.job$$";
my $qsuberr="$workingdir/err.job$$";

my $cfg_file=""; #configuration file

die "** ERROR: Environment variable KRIYA_DIR undefined. Exiting!!\n" if(!defined $ENV{KRIYA_DIR});
my $kriya_home = $ENV{KRIYA_DIR};
my $decoder_prefix = "/home/msiahban/Modules/PYTHON/2.6.2/bin/python";
my $decoder_dir = "${kriya_home}/Hiero-Decoder-Shallow";
my $decoder_cmd = "${decoder_dir}/decoder.py";

my $cfgfile=undef;
my $zmert_cfgfile=undef;
my $inputdir=undef;
my $outputdir=undef;
my $ruledir=undef;
my $ttable = undef;
my $lm_file=undef;
my $nbestlist="nbest.kriya.out";
my $nbestsize=undef;
my $nbestflag=1;
my $jobs=undef;
my $sent_per_job=200;
my $decoder_params=undef;

my $robust=1; # undef; # resubmit crashed jobs
my $mert_status= 100;  # Three digit code to indicate the current state of the 'mert' and has the structure:
                       # <Iteration no, decoding status, concatenation of nbest status>; default: 100
                       # iteration is 1 or above, status digit 0 means not begun, 1 means partly completed
my $prev_jobid;        # Used to specify the job-id when mert was aborted
my $qsubname="KRIYA";

my $queue_params="-l__mem=8gb,pmem=8gb,pvmem=8gb,walltime=4:30:00";
my $nodes_prop="-l__nodes=1:ppn=1";

my $logfile=undef;
my $logflag=0;


###################
# Command line options processing
sub init(){
    use Getopt::Long qw(:config pass_through no_ignore_case permute);
    GetOptions('version'=>\$version,
	       'help'=>\$help,
	       'debug'=>\$dbg,
	       'decoder=s'=> \$decoder_cmd,
	       'decoder-prefix=s'=>\$decoder_prefix,
	       'robust' => \$robust,
	       'mert-status=i' => \$mert_status,
	       'prev-jobid=i' => \$prev_jobid,
	       'decoder-parameters=s'=> \$decoder_params,
	       'i|inputdir|input-dir=s'=> \$inputdir,
	       'output-dir=s' => \$outputdir,
	       'rule-dir=s' => \$ruledir,
	       'ttable-file=s' => \$ttable,
	       'lmfile=s' => \$lm_file,
       	       'n-best-size=i'=> \$nbestsize,
	       'jobs=i'=>\$jobs,
	       'sent-per-job=i'=>\$sent_per_job,
	       'qsub-prefix=s'=> \$qsubname,
	       'nodes-prop=s' => \$nodes_prop,
	       'queue-parameters=s'=> \$queue_params,
	       'config|f=s'=>\$cfgfile,
	       'zmert-config=s'=>\$zmert_cfgfile,
	       ) or exit(1);

#    print_parameters();
#    print STDERR "nbestflag:$nbestflag\n";
#    print STDERR "inputdir:$inputdir\n";
}


###################
## Print version
sub version(){
    print STDERR "version 3.0 (12-2010)\n";
    exit(1);
}

# Usage
sub usage(){
    print STDERR "decode_with_kriya.pl [Parallel-options] [Kriya-options]\n";
    print STDERR "Options marked (*) are required.\n";
    print STDERR "Parallel options:\n";
    print STDERR "*  -decoder <file>   decoder executable to use\n";
    print STDERR "*  -decoder-prefix <prefix>   prefix used for executing decoder (any interpretor etc.)";
    print STDERR "*  -i|inputdir|input-dir <dir>   directory having the input files to translate\n";
    print STDERR "*  -output-dir <dir>   directory for writing the output files\n";
    print STDERR "*  -rule-dir <dir>   directory having the SCFG rule files corresponding to the input files\n";
    print STDERR "*  -lmfile <file>   LM file to be used for decoding";
    print STDERR "*  -jobs <N>   number of required jobs\n";
    print STDERR "   -sent-per-job <N>   number of sentences per job\n";
    print STDERR "   -qsub-prefix <string>   name for sumbitte jobs\n";
    print STDERR "   -queue-parameters <string>   specific requirements for queue\n";
    print STDERR "   -version   print version of the script\n";
    print STDERR "   -help   this help\n";
    print STDERR "Kriya options:\n";
    print STDERR "   -n-best-size <N>   size of nbest list (default 100)\n";
    print STDERR "*  -config (f) <cfgfile>   configuration file\n";
    print STDERR "*  -zmert-config <zmert-cfgfile>   zmert configuration file\n";
    print STDERR "   -decoder-parameters <string>   specific parameters for the decoder\n";
    exit(1);
}

# Print the parameters
sub print_parameters(){
    print STDERR "Input directory: $inputdir\n";
    print STDERR "Rule directory: $ruledir\n" if (defined $ruledir);
    print STDERR "T-table file: $ttable\n" if (defined $ttable);
    print STDERR "Output directory: $outputdir\n";
    print STDERR "LM file: $lm_file\n";
    print STDERR "Configuration file: $cfgfile\n";
    print STDERR "Zmert config file: $zmert_cfgfile\n";
    print STDERR "Decoder in use: $decoder_cmd\n";
    print STDERR "Decoder prefix: $decoder_prefix\n";
    print STDERR "Number of jobs:$jobs\n";
    print STDERR "Number of sentences per job:$sent_per_job\n";
    print STDERR "Nbest list: $nbestlist\n" if ($nbestflag);
    print STDERR "Qsub name: $qsubname\n";
    print STDERR "Nodes properties: $nodes_prop\n";
    print STDERR "Queue parameters: $queue_params\n";

    print STDERR "parameters directly passed to Kriya: $decoder_params\n";
}



#######################
#Script starts here

init();
#exit(0);

version() if $version;
usage() if $help;

# $mert_status can't be used with zmert
=begin
if ($mert_status =~ /\d11/) {
    print  STDERR "ERROR: Both the second and third digits in ($mert_status) can not be 1. Exiting!!\n";
    exit(1);
}

if ($mert_status != 100 && !defined $prev_jobid) {
    print STDERR "ERROR: Iteration specified as ($mert_status)\n";
    print STDERR "Error: To continue this iteration please specify the id for the previous job. Exiting!!\n";
    exit(1);
}
=cut

if (!defined $inputdir || !defined $decoder_cmd || ! defined $cfgfile) {
    print STDERR "Please specify -input-dir, -decoder and -config\n";
    usage();
}

#checking if inputdir exists
if (! -e ${inputdir} ){
    print STDERR "Input directory ($inputdir) does not exists\n";
    usage();
}

#checking if decoder exists
if (! -e $decoder_cmd) {
    print STDERR "Decoder ($decoder_cmd) does not exists\n";
    usage();
}

#checking if configfile exists
if (! -e $cfgfile) {
    print STDERR "Configuration file ($cfgfile) does not exists\n";
    usage();
}

if (defined $decoder_prefix) { $decoder_prefix =~ s/\=/ /; }
if (defined $queue_params) { $queue_params =~ s/__/ /; }
if (defined $nodes_prop) { $nodes_prop =~ s/__/ /; }

if ($dbg) { 
    print_parameters();  # debug mode: just print and do not run
    exit(1);
}


my $cmd;
my $in_file;
my $rule_file;
my $out_file;
my $status_file;

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


if ($run > 1) {
    $cfgfile =~ s/(run)\d+(\.)/$1$run$2/;
}

@idx_todo = @idxlist;
safesystem("mkdir -p $tmpdir") or die;
$status_file = $tmpdir."/mert_status.out";

copy_zmert_weights();       # Copy the newly updated zmert weights into Kriya's config-file ($cfgfile)

# Back-up the $cfgfile before the iteration begins
my($cfg_base, $directories) = fileparse($cfgfile);
safesystem("cp $cfgfile ${directories}run${run}.${cfg_base}") or die;


preparing_script();         # Prepare scripts for decode jobs
submit_jobs();              # Submit decode jobs in cluster

merge_nbest();              # Concatenate the nbest files

store_mert_runid();         # Store the current run-id

exit(0);


# Get the MERT run-id
sub get_mert_runid() {
    my $comp_step;

    if (!-e "finished_step.txt") { $comp_step = 0; }
    else {
        open(RUN, "finished_step.txt") || die "Cannot open finished_step.txt for reading. Exiting!!";
        chomp( $comp_step = <RUN> );
        close(RUN);
    }
    return $comp_step + 1;    # Increment the completed step by '1' for current run
}

sub copy_zmert_weights() {
    my $line;
    my @kriya_cfg = ();
    my @tm_wgts = ();
    my %feat_hsh = ();

    # Read Kriya config file to an array
    open(KCFG, "$cfgfile") || die "Cannot open Kriya's config file: $cfgfile for reading. Exiting!!";
    @kriya_cfg = <KCFG>;
    close(KCFG);

    # Now get the updated weights from zmert config file into a hash
    open(ZCFG, "$zmert_cfgfile") || die "Cannot open zmert's config file for reading. Exiting!!";
    while(<ZCFG>) {
        chomp;
        next if (/^\#/ || /^\s*$/);

        if ($_ =~ /^weight_tm/) {
            s/([^\s]+)\s+([^\s]+)/push(@tm_wgts, $2);/e;
        }
        else {
            s/(weight_.*?)\s+(\-?\d?\.\d+)$/$feat_hsh{$1}=$2;/e;
        }
    }
    close(ZCFG);

    # Now create Kriya config file with newly updated weights from zmert config file
    open(KCFG, ">$cfgfile") || die "Cannot open Kriya's config file: $cfgfile for writing. Exiting!!";
    for (my $l_idx = 0; $l_idx < scalar(@kriya_cfg); $l_idx++) {
        chomp( $line = $kriya_cfg[$l_idx] );
        if ( $line =~ /^\[weight_tm\]/ ) {
            print KCFG "$line\n";
            foreach (@tm_wgts) { print KCFG "$_\n"; }
            $l_idx += 5;
	}
        elsif ( $line =~ /\[weight_/ ) {
	    print KCFG "$line\n";
            $line =~ s/[\[\]]//g;
            print KCFG $feat_hsh{$line},"\n";
            ++$l_idx;
	}
        else { print KCFG "$line\n"; }
    }
    close(KCFG);
}


# launching process through the queue and if robust switch is used, redo jobs that crashed
sub submit_jobs() {

    my $looped_once = 0;
    my $job_cnt = 0;
    while((!$robust && !$looped_once) || ($robust && scalar @idx_todo)) {
	$looped_once = 1;
	my $idx = shift(@idx_todo);
	$job_cnt++;
	print STDERR "Job# $job_cnt >> ";
	$cmd="qsub $nodes_prop $queue_params -m a -M bsa33\@sfu.ca -o $qsubout$idx -e $qsuberr$idx -N $qsubname$idx ${jobscript}${idx}.sh >& ${jobscript}${idx}.log";
	print STDERR "$cmd\n" if $dbg;
	safesystem($cmd) or die;

	my ($res,$id);
	open (IN,"${jobscript}${idx}.log") or die "Can't read id of job ${jobscript}${idx}.log";
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
    concatenate_logs() if $logflag;
    concatenate_nbest() if $nbestflag;
    remove_temporary_files();
}


sub store_mert_runid() {
    open(RUN, ">finished_step.txt") || die "Cannot open finished_step.txt for writing. Exiting!!";
    print RUN "$run\n";
    close(RUN);
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
	sleep(300);
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


# Script creation
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
        #print OUT "source /hpc/software/etc/colony-login\n";
        #print OUT "module load LANG/PYTHON/2.6.2\n\n";
        #print OUT "source /cs/natlang-sw/etc/natlang-login\n";
        #print OUT "module load NL/LANG/PYTHON/2.6.2\n\n";

	my $sent_indx = $idx - 1;
	## ********* ONLY FOR DEBUGGING ********* ##
	#print OUT "$decoder_prefix $decoder_cmd $out_file > $tmpdir/run_$idx.out\n\n";

	print OUT "$decoder_prefix $decoder_cmd --config $cfgfile --zmert-nbest --index $sent_indx --sentperfile $sent_per_job --inputfile $in_file --outputfile $out_file --ttable-file $rule_file --lmodel-file $lm_file >& $tmpdir/run_$idx.out\n\n";
	print OUT "echo exit status \$\?\n\n";

	#print OUT "module unload LANG/PYTHON/2.6.2\n\n";
	#print OUT "echo exit status \$\?\n\n";
	close(OUT);

	#setting permissions of each script
	chmod(oct(755),"${jobscript}${idx}.sh");
    }
}

sub concatenate_nbest(){
    my $outnbest="run${run}.nbest.out";

    foreach my $idx (@idxlist){
	$out_file = $tmpdir."/".$idx.".out";
	safesystem("cat $out_file >> $outnbest") or kill_all_and_quit();
    }

    safesystem("cp $outnbest $nbestlist") or die;
    safesystem("gzip $outnbest") or die;
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
    for(my $i=0; $i<@idx_submitted; $i++){
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
	unlink("$tmpdir/run_$idx.out");
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
