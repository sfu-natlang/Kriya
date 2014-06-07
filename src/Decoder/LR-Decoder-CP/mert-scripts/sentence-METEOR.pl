#! /usr/bin/perl

use Cwd 'abs_path';
use File::Basename;

use strict;

my $robust = 1;
my $queueparameters = "-l mem=3gb,vmem=3gb,walltime=0:30:00";

my $pwdcmd = getPwdCmd();

my $help = undef;
my $run = undef;
my $stem = undef;
my $NBest_file = undef;
my $lang = "en";

my $workingdir = `$pwdcmd`; chomp $workingdir;
$workingdir =~ s/\/$//;
my $metric_dir = undef;
my $split_dir = undef;
my $status_file;

my $scrpt_dir = $workingdir;
my $jobscript = "${scrpt_dir}/meteor.set";
my $qsubout="${workingdir}/out.meteor";
my $qsuberr="${workingdir}/err.meteor";
my $qsubname = "METEOR-set";
my $tot_refs = 0;

my @job_ids = ();
my @idxlist = ();
my @idx_todo = ();
my @idx_status = ();
my @idx_submitted = ();

init();
usage() if $help;
METEOR_Sent();

sub init(){
    use Getopt::Long;
    GetOptions(
	    'help'=>\$help,
	    'run=i'=>\$run,
	    'ref-stem=s'=> \$stem,
	    'nbest-file=s'=>\$NBest_file,
        'metric-dir=s'=>\$metric_dir,
	    ) or exit(1);
}

sub usage(){
    print STDERR "sentence-METEOR.pl [options]\n";
    print STDERR "Options marked (*) are required.\n";
    print STDERR "*  -run <index> ... index of the current run\n";
    print STDERR "*  -ref-step <string> ... stem or file name for refenrence(s)\n";
    print STDERR "*  -nbest-file <file> ... n-best file name\n";
    print STDERR "*  -metric-dir <directory> ... path for the Metric stats\n";
    exit(1);
}

sub METEOR_Sent {
    $split_dir = "${metric_dir}/meteor-splits";
    safesystem("mkdir -p $split_dir") if (!-e $split_dir);

    my @REF;
    if ($stem =~ /,/) {
        foreach my $ref_file (split(/,/, $stem)) {
            &add_to_ref($ref_file,\@REF);
            $tot_refs++;
        }
    }
    else {
        $stem .= ".ref" if !-e $stem && !-e $stem."0" && -e $stem.".ref0";

        my $ref=0;
        while(-e "$stem$ref") {
            &add_to_ref("$stem$ref",\@REF);
            $ref++;
            $tot_refs++;
        }
        if (-e $stem) {
            &add_to_ref($stem,\@REF);
            $tot_refs++;
        }
    }

    print STDERR "\nCollecting sufficient stats for METEOR from N-best file ...\n";
    open (HYP, "<:encoding(utf8)", $NBest_file) or die "Can't read $NBest_file";
    my $set_indx = 0;
    my $set_size = 500;
    my $tot_sents = 0;
    my $prev_refNum = -1;
    my $out;
    ##open ($out, ">:utf8", "${metric_dir}/meteor.dat") or die "Can't open ${metric_dir}/meteor.dat: $!";
    while (<HYP>){
        chomp;
        my @PARTS=split(/\s*\|\|\|\s/,$_);
        my $hyp = $PARTS[1];
        my $refNum = $PARTS[0];

        if ($tot_sents % $set_size == 0 && $prev_refNum != $refNum) {
            if ($set_indx != 0) {
                close $out or die "$out: $!";
            }
            $set_indx++;
            open ($out, ">:utf8", "${split_dir}/run${run}.${set_indx}.out") or die "Can't open ${split_dir}/run${run}.${set_indx}.out: $!";
        }

        my $thisReferenes = $REF[$refNum];
        print $out "SCORE ||| ";
        foreach my $reference (@{$thisReferenes}) {
            print $out "${reference} ||| ";
        }
        print $out "${hyp}\n";
        if ($prev_refNum != $refNum) {
            $tot_sents++;
            $prev_refNum = $refNum;
        }
    }
    close(HYP);
    close $out or die "$out: $!";

=b
    ## Run the split directly without qsub
    my $meteor_scr = abs_path(dirname($0))."/run_meteor.sh";
    my $cmd = "$meteor_scr $lang ${metric_dir}/meteor.dat ${metric_dir}/meteor.stats ${metric_dir}/meteor.eval ${metric_dir}/meteor.out.meteor";
    safesystem($cmd) or die;
=cut

    prepare_scripts($run, $set_indx, $split_dir);
    submit_jobs();
    merge_meteor_files($set_indx);
    remove_temporary_files();
}

sub add_to_ref {
    my ($file,$REF) = @_;
    my $s=0;
    open(REF, "<:encoding(utf8)", $file) or die "Can't read $file";
    while(<REF>) {
        chomp;
        push @{$$REF[$s++]}, $_;
    }
    close(REF);
}

sub prepare_scripts {
    my ($run, $tot_sets, $split_dir) = @_;
    my $cmd;
    @idx_todo = ();

    my $meteor_scr = abs_path(dirname($0))."/run_meteor.sh";
    for (my $idx = 1; $idx <= $tot_sets; $idx++) {
        push @idx_todo, $idx;

        open(OUT, ">${jobscript}${idx}.sh");
        print OUT "#! /bin/bash\n\n";
        print OUT "$meteor_scr $lang ${split_dir}/run${run}.${idx}.out ${split_dir}/stats.${idx}.stats ${split_dir}/eval.${idx}.eval ${split_dir}/meteor.${idx}.meteor\n\n";
        print OUT "echo exit status \$\?\n\n";
        close(OUT);
    }
    @idxlist = @idx_todo;
}

sub submit_jobs() {

    my $looped_once = 0;
    my $job_cnt = 0;
    my $cmd;
    while((!$robust && !$looped_once) || ($robust && scalar @idx_todo)) {
	  $looped_once = 1;
	  my $idx = shift(@idx_todo);
	  $job_cnt++;
      unlink("$qsubout$idx") if (-e "$qsubout$idx");

	  #print STDERR "Job# $job_cnt >> ";
	  $cmd="qsub $queueparameters -o $qsubout$idx -e $qsuberr$idx -N $qsubname$idx ${jobscript}${idx}.sh >& ${jobscript}${idx}.log";
	  #print STDERR "$cmd\n";
	  safesystem($cmd) or die;

	  my ($res,$id);
	  open (IN,"${jobscript}${idx}.log") or die "Can't read id of job ${jobscript}${idx}.log";
	  chomp($res=<IN>);
	  ($id) = split(/\./,$res);
	  close(IN);

	  push @job_ids,$id;
	  push @idx_status,99;
	  push @idx_submitted,$idx;

	  if(scalar(@idx_todo) == 0) {
	    wait_for_completion(join(":", @job_ids));
	    @job_ids = ();
	    @idx_status = ();
	    @idx_submitted = ();
	  }
	  last if !scalar(@idx_todo);          # exit the loop if all the jobs are done
      sleep(1);
    }
}

sub wait_for_completion() {
    my $hj = shift;    #waiting until all these jobs have finished

    # use the -W depend=afterok option for qsub
    my $syncscript = "$qsubname.W.sh";
    safesystem("echo '/bin/ls' > $syncscript") or kill_all_and_quit();
    my $cmd="qsub -l mem=200m -l walltime=00:03:00 -W depend=afterok:$hj -j oe -o $qsubname.W.err -e $qsubname.W.err -N $qsubname.W $syncscript >& $qsubname.W.log";
    safesystem($cmd) or kill_all_and_quit();

    my $failure = 1;
    print STDERR "Waiting for jobs to complete: checking exit status ...\n";
    while ($failure) {
        $failure=&check_exit_status();
        last if !$failure;
        sleep(30);
    }
    sleep(30);  # Extra wait for possibly unfinished processes

    kill_all_and_quit() if $failure && !$robust;

    # check if some translations failed
    my @idx_still_todo = ();
    @idx_still_todo = check_meteor_output();
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
                    elsif (/exit status 1$/ || /exit status 137/) {
                        push @idx_todo,$idx;
                        $failure=0;
                        last;
                    }
	            }
		        close(IN);
		        #unlink("$qsubout$idx") if (!$failure);
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
    foreach my $id (@job_ids){
	print STDERR "canceljob $id\n";
	safesystem("canceljob $id");
    }
    print STDERR "METEOR score computation did not complete correctly\n";
    print STDERR "or some of the submitted jobs died.\n";
    print STDERR "canceljob function was called for all submitted jobs\n";

    exit(1);
}

sub check_meteor_output(){
    #check each set to verify that METEOR scores are found for all sentences in the set
    my $inputN;
    my $outputN;
    my $emptyN;
    my @failed = ();
    $status_file = $split_dir."/meteor_status.out";
    open(MS, ">>$status_file") or die "Can't read file METEOR status file: ($status_file)";
    foreach my $idx (@idx_submitted){
	my $in_file = "${split_dir}/run${run}.${idx}.out";
	my $out_file = "${split_dir}/meteor.${idx}.meteor";
	if (!-e "$out_file") { push @failed,$idx; next; }

	chomp($inputN=`wc -l ${in_file} | cut -d' ' -f1`);
	chomp($outputN=`wc -l ${out_file} | cut -d'|' -f1`);
	chomp($emptyN=`grep -c '^\$' ${out_file}`);

	if ($inputN != $outputN || $emptyN){
	    print STDERR "METEOR scores were not fully computed for split ($idx)\n";
	    print STDERR "outputN=$outputN inputN=$inputN Empty scores=$emptyN\n";
	    print STDERR "outputfile=${out_file} inputfile=${in_file}\n";

	    print "METEOR scores were not fully computed for split ($idx)\n";
	    print "outputN=$outputN inputN=$inputN Empty scores=$emptyN\n";
	    print "outputfile=${out_file} inputfile=${in_file}\n";
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

sub merge_meteor_files {
    my $tot_sets = shift;
    my $meteor_file = "${metric_dir}/meteor.out.meteor";
    for (my $idx = 1; $idx <= $tot_sets; $idx++) {
	    my $out_file = "${split_dir}/meteor.${idx}.meteor";
        safesystem("cat $out_file > $meteor_file") if ($idx == 1);
        safesystem("cat $out_file >> $meteor_file") if ($idx > 1);
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

sub remove_temporary_files(){
    #removing temporary files
    foreach my $idx (@idxlist){
	    unlink("$split_dir/run$run.$idx.out");
	    unlink("$split_dir/stats.$idx.stats");
	    unlink("$split_dir/eval.$idx.eval");
	    unlink("$split_dir/meteor.$idx.meteor");
    	unlink("$jobscript$idx.sh");
	    unlink("$jobscript$idx.log");
    	unlink("$qsubout$idx");
	    unlink("$qsuberr$idx");
    }
	unlink("$qsubname.W.sh");
	unlink("$qsubname.W.log");
	unlink("$qsubname.W.err");
    my $status_file = "${split_dir}/meteor_status.out";
    if (-e $status_file) { unlink("$status_file"); }
}

sub safesystem {
    print STDERR "Executing: @_\n";
    system(@_);
    if ($? != 0) { die "Failed executing [@_]\n"; }

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
1;
