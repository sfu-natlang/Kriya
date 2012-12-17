#! /usr/bin/perl

## Perl script for executing different steps in SCFG rule extraction ##
## Note: The memory and walltime requirements for 'qsub' are set for 1.6 million setence pairs
## Scale these numbers accordingly for the size of the corpus

use Cwd 'abs_path';
use File::Basename;
use lib dirname(abs_path($0));
use POSIX;

use TrainConfig;
use strict;
use warnings;

my $config_file = abs_path($ARGV[0]);

if (!defined $config_file) { die "usage: $0 <Training config file>\nSpecify a training config file. Exiting!\n"; }
if (!-e $config_file) { die "Training config file $config_file does not exist. Exiting!\n"; }

my $cfg = TrainConfig->new($config_file);
if (!defined $cfg->{TRAIN_DIR}) { die "ERROR: TRAIN_DIR parameter must be specified for Kriya model training. Exiting!\n"; }
if (!-e $cfg->{LC_TRAIN_DIR}) { die "ERROR: $cfg->{LC_TRAIN_DIR} doesn't exist. Exiting!\n"; }
&check_moses_path();

# Directories
my $model_root = $cfg->{KRIYA_MODELS};                                  # training - root directory
my $rules_dir = "$model_root/training/scfg-rules";                      # where to write the extracted scfg rules
my $model_dir = "$model_root/model";                                    # where to create the models

my $corpus_dir = $cfg->{LC_TRAIN_DIR};                                  # training data directory
my $phr_align_dir = "$model_root/training/phr-alignments";
my $lex_dir = "$phr_align_dir/model";                                   # lexical models (Giza training) dir

my $codeDir   = $cfg->{KRIYA_PXTR};
my $logDir    = "$model_root/log";
my $scrptDir  = "$model_root/scripts";

# Create necessary directories
safeSystem("mkdir $rules_dir") unless -e $rules_dir;
safeSystem("mkdir $model_dir") unless -e $model_dir;

safeSystem("mkdir $logDir") unless -e $logDir;
safeSystem("mkdir $scrptDir") unless -e $scrptDir;
safeSystem("mkdir -p $phr_align_dir/moses/split-data") unless -e "$phr_align_dir/moses/split-data";

# Global parameters
my $src = $cfg->{src};
my $tgt = $cfg->{tgt};
my $pre = "all.$src-$tgt";
my $fr_terms = $cfg->{fr_side_len};
my $non_terms = $cfg->{non_terminals};

my $tot_files = &how_many_parts("$corpus_dir/$pre.$src", $cfg->{split_size});
print STDERR "Total input files for rule extraction : $tot_files\n";

my $log_n_notify = "-e $logDir -o $logDir";                     # Notifier string for 'qsub'
$log_n_notify .= " ". $cfg->{qsub_notify} if (defined $cfg->{qsub_notify});

my $currset_src;
my $currset;
my $devset_split = 0;
my $testset_split = 0;

# Other variables
my $idx;                                # Job index
my $step1_jobs = "";                    # Job dependencies for step-2 jobs for both devset and testset
my $pstep_jobs = "";                    # ':' separated job-ids for the jobs executed in the previous step
my @idx_submitted = ();                 # Array for the submitted job-ids
my @idx_completed = ();                 # Array for the completed job-ids
my @last_step_jobs = ();                # Array of the job-ids submitted in the last extraction step

my $xtrct_scr = "$scrptDir/extract.sh";
my $split_scr = "$scrptDir/split.sh";
my $ph1_scr;
my $ph1b_scr;
my $ph2a_scr;
my $ph2b_scr;
my $ph2c_scr;
my $ph3_scr;
my $ph4a_scr;
my $ph4b_scr;
my $mert_meta_scr = "$scrptDir/get_mert_files.sh";
my $del_scr = "delete_temp_files.sh";

# Run the model training in phases
foreach my $set ( reverse( split(/,/, $cfg->{STEPS}) ) ) {
    my $set_lc_dir = "LC_${set}_DIR";

    if ($set eq 'TRAIN') {
        print STDERR "\nRunning SCFG Rule extraction on $set set ...\n";
        &step_0();
        &step_1();
        &step_1b();
        if (!defined $cfg->{LC_DEV_DIR} && !defined $cfg->{LC_TEST_DIR}) {
            print STDERR "Neither DEV_DIR not TEST_DIR are specified.\nSCFG rule extraction is complete and Kriya model training will not continue. Exiting!\n";
            exit(0);
        }
    }
    else {
        my $lc_set = lc($set);
        my $set_pre = "${set}_PRE";
        $currset_src = "$cfg->{$set_lc_dir}/$cfg->{$set_pre}.$src";
        my $set_parts = &how_many_parts($currset_src, $cfg->{sent_per_file});
        if ($lc_set eq "dev") { $devset_split = $set_parts; }
        else { $testset_split = $set_parts; }

        $currset = "${lc_set}set";
        &step_2($lc_set);
        &step_2c($lc_set);
        &step_3($lc_set);
        &step_4($lc_set);
        push(@last_step_jobs, @idx_submitted);
    }
}
if (!defined $cfg->{LC_DEV_DIR} || !defined $cfg->{LC_TEST_DIR}) {
    print STDERR "Skipping the step that createst mert files. Both DEV_DIR and TEST_DIR are required for creating MERT files. Exiting!\n";
    exit(0);
}
&create_mert_files();
#&delTempFiles();


sub check_moses_path {
    if (!defined $cfg->{'MOSES_SCRIPTS'}) {
        print STDERR "ERROR: Parameter MOSES_SCRIPTS must be set in the config file.\n";
        print STDERR "\tPlease point it to the MOSES Scripts directory before launching $0. Exiting!\n";
        exit(1);
    }
    if (defined $ENV{'MOSES_DIR'} || defined $ENV{'SCRIPTS_ROOTDIR'}) {
        die "Moses module appears to be loaded. Please unload this before proceeding. Exiting!\n";
    }
}

sub how_many_parts {
    my $corpus_file = shift;
    my $split_size = shift;
    my $tot_sent = &get_corpus_size($corpus_file);
    return ceil($tot_sent / $split_size);
}

sub get_corpus_size {
    my $corpus_file = shift;
    my($tot_sent, $file) = split( /\s+/, `/usr/bin/wc -l $corpus_file` );
    $tot_sent =~ s/(^\s+|\s+$)//g;
    return $tot_sent;
}


# Step-0: a.Extract initial phrase alignments (use moses command: extract); b.Split training data into smaller sets #
sub step_0 {
    my $en    = "$corpus_dir/$pre.$tgt";
    my $de    = "$corpus_dir/$pre.$src";
    my $max_phr_len   = $cfg->{max_phr_len};
    my $align = "$lex_dir/aligned.grow-diag-final-and";
    my $outspan = "$phr_align_dir/moses/$pre.outspan";

    # a. Extract initial phrase alignments (use moses command: extract)
    my $xtrct_cmd = "$cfg->{MOSES_SCRIPTS}/training/phrase-extract/extract $en $de $align temp.$src-$tgt $max_phr_len --OnlyOutputSpanInfo > $outspan";
    writeCmd2File($xtrct_scr, $xtrct_cmd);

    safeSystem("qsub -l mem=2gb,walltime=1:00:00 -N extract_init_align $log_n_notify $xtrct_scr >& $xtrct_scr.log");
    $idx = getJobId("$xtrct_scr.log");
    push @idx_submitted, $idx;

    # b. Split training data into smaller sets to extract scfg parallely
    $pstep_jobs = join(":", @idx_submitted);
    @idx_submitted = ();
    my $split_cmd = "python $codeDir/pre-process/splitDataFile.py $cfg->{split_size} $outspan $phr_align_dir/moses/split-data";
    writeCmd2File($split_scr, $split_cmd);

    safeSystem("qsub -l mem=1gb,walltime=1:00:00 -W depend=afterok:$pstep_jobs -N split_corpus $log_n_notify $split_scr >& $split_scr.log");
    $idx = getJobId("$split_scr.log");
    push @idx_submitted, $idx;
}


# Step-1: Extract SCFG rules from initial phrasal alignments #
sub step_1 {
    my $ph1_cmd;
    $pstep_jobs = join(":", @idx_submitted);
    @idx_submitted = ();
    my $one_NT = ($non_terms == 1) ? 'True' : 'False';

    $ph1_scr = "$scrptDir/phase1.sh";
    $ph1_cmd = "python $codeDir/SCFGXtractor_ph1.py \$j $phr_align_dir/moses/split-data $rules_dir $fr_terms $one_NT";
    writeCmd2File($ph1_scr, $ph1_cmd);

    # Multiple jobs should be submitted (one for each file in the split-set)
    print STDERR "Extracting SCFG rules from files ...\n\n";
    for (my $i=1; $i<=$tot_files; $i++) {
        safeSystem("qsub -l mem=8gb,walltime=6:00:00 -W depend=afterok:$pstep_jobs -N ph1-$i $log_n_notify -v j=$i $ph1_scr >& $scrptDir/phase1.$i.log");
        $idx = getJobId("$scrptDir/phase1.$i.log");
        push @idx_submitted, $idx;
        sleep(1);
    }
    $step1_jobs = join(":", @idx_submitted);
}

# Step-1b: Consolidate (unfiltered) tgt counts
sub step_1b {
    $pstep_jobs = join(":", @idx_submitted);
    @idx_submitted = ();

    # Multiple jobs should be submitted (one for each file in the split-set)
    print STDERR "Merging Tgt counts from files ...\n\n";
    my $ph1b_cmd = "python $codeDir/mergeTgtCounts.py $rules_dir";
    $ph1b_scr = "$scrptDir/phase1b.sh";
    my $ph1b_log = "$scrptDir/phase1b.log";
    writeCmd2File($ph1b_scr, $ph1b_cmd);

    safeSystem("qsub -l mem=1gb,walltime=8:00:00 -W depend=afterok:$pstep_jobs -N ph1b-$src-$tgt $log_n_notify $ph1b_scr >& $ph1b_log");
    $idx = getJobId("$ph1b_log");
    push @idx_submitted, $idx;
    sleep(1);
    $pstep_jobs = join(":", @idx_submitted);
}

# Step-2: Filter the generated SCFG rules for a given tuning/test set and consolidate their counts; also compute forward & reverse lexical probs #
sub step_2 {
    my $set = shift;
    $ph2a_scr = "$scrptDir/$set.phase2a.sh";
    @idx_submitted = ();
    safeSystem("mkdir $rules_dir/$currset-temp");
    safeSystem("mkdir $rules_dir/$currset-filtered");

    # Step-2a: Filter the generated SCFG rules for a given tuning/test set
    my $ph2a_cmd = "python $codeDir/SCFGXtractor_ph2a.py $currset_src \$j $rules_dir $rules_dir/$currset-temp $fr_terms";
    writeCmd2File($ph2a_scr, $ph2a_cmd);

    for (my $i=1; $i<=$tot_files; $i++) {
        safeSystem("qsub -l mem=10gb,walltime=3:00:00 -W depend=afterok:$step1_jobs -N $set-ph2a-$i $log_n_notify -v j=$i $ph2a_scr >& $scrptDir/$set.phase2a.$i.log");
        $idx = getJobId("$scrptDir/$set.phase2a.$i.log");
        push @idx_submitted, $idx;
        sleep(1);
    }
    $pstep_jobs = join(":", @idx_submitted);

    # Merge the filtered rule files and consolidate their counts; also compute forward & reverse lexical probs #
    $ph2b_scr = "$scrptDir/$set.phase2b.sh";
    @idx_submitted = ();
    my $ph2b_cmd = "python $codeDir/SCFGXtractor_ph2b.py $rules_dir/$currset-temp $rules_dir/$currset-filtered $lex_dir/lex.f2e $lex_dir/lex.e2f";
    writeCmd2File($ph2b_scr, $ph2b_cmd);

    safeSystem("qsub -l mem=3gb,walltime=6:00:00 -W depend=afterok:$pstep_jobs -N $set-ph2b $log_n_notify $ph2b_scr >& $scrptDir/$set.phase2b.log");
    $idx = getJobId("$scrptDir/$set.phase2b.log");
    push @idx_submitted, $idx;
    $pstep_jobs = join(":", @idx_submitted);
    print STDERR "Completed submitting jobs for Phase-2 of SCFG rules extraction.\n";
}

# Step-2c: Filter the consolidated tgt counts for a given dev/test set.
sub step_2c {
    my $set = shift;
    $pstep_jobs = join(":", @idx_submitted);
    @idx_submitted = ();

    print STDERR "Filter the target rules relevant for a filtered set of rules ...\n\n";
    my $ph2c_cmd = "python $codeDir/filterTgtCounts.py $rules_dir/tgt_rules.all.out $rules_dir/$currset-filtered/rules_cnt_align.out $rules_dir/$currset-filtered/tgt_rules.all.out";
    $ph2c_scr = "$scrptDir/$set.phase2c.sh";
    writeCmd2File($ph2c_scr, $ph2c_cmd);

    safeSystem("qsub -l mem=1gb,walltime=10:00:00 -W depend=afterok:$pstep_jobs -N $set-ph2c $log_n_notify $ph2c_scr >& $scrptDir/$set.phase2c.log");
    $idx = getJobId("$scrptDir/$set.phase2c.log");
    push @idx_submitted, $idx;
    sleep(1);
    $pstep_jobs = join(":", @idx_submitted);
}

# Step-3: Compute forward and reverse probs; write the log-prob values of 4 features #
sub step_3 {
    my $set = shift;
    $ph3_scr = "$scrptDir/$set.phase3.sh";
    my $ph3_cmd = "python $codeDir/SCFGXtractor_ph3.py $rules_dir/$currset-filtered/rules_cnt_lprob.out rules_cnt.final.out";
    writeCmd2File($ph3_scr, $ph3_cmd);

    safeSystem("qsub -l mem=8gb,walltime=2:00:00 -W depend=afterok:$pstep_jobs -N $set-ph3 $log_n_notify $ph3_scr >& $scrptDir/$set.phase3.log");
    $idx = getJobId("$scrptDir/$set.phase3.log");
    push @idx_submitted, $idx;
    print STDERR "Completed submitting jobs for Phase-3 of SCFG rules extraction.\n";
}


# Step-4: Split and filter rules for dev/ test-set
sub step_4 {
    my $set = shift;
    $ph4a_scr = "$scrptDir/$set.phase4a.sh";
    # 4(a): Split the dataset into smaller sets of 100 sentences each
    $pstep_jobs = join(":", @idx_submitted);
    @idx_submitted = ();

    my $sent_dir = "$model_dir/$currset-sent";
    my $filt_rules_dir = "$model_dir/$currset-rules";
    safeSystem("mkdir $sent_dir");
    safeSystem("mkdir $filt_rules_dir");
    my $ph4a_cmd = "python $cfg->{KRIYA_DEC}/pre-process/splitDataFile.py $currset_src $sent_dir $cfg->{sent_per_file}";
    writeCmd2File($ph4a_scr, $ph4a_cmd);

    safeSystem("qsub -l mem=2gb,walltime=1:00:00 -W depend=afterok:$pstep_jobs -N $set-ph4a $log_n_notify $ph4a_scr >& $scrptDir/$set.phase4a.log");
    $idx = getJobId("$scrptDir/$set.phase4a.log");
    push @idx_submitted, $idx;
 
    # 4(b): Filter for smaller sets (as specified by the 1^st argument)
    $ph4b_scr = "$scrptDir/$set.phase4b.sh";
    $pstep_jobs = join(":", @idx_submitted);
    my $set_parts = ($set eq "dev") ? $devset_split : $testset_split;
    @idx_submitted = ();

    my $py_scrpt = "$cfg->{KRIYA_DEC}/pre-process/sufTreeFilter.py";
    my $ph4b_cmd = "python $py_scrpt \$j $rules_dir/$currset-filtered/rules_cnt.final.out $sent_dir $filt_rules_dir $fr_terms";
    writeCmd2File($ph4b_scr, $ph4b_cmd);

    for (my $i=1; $i<=$set_parts; $i++) {
        safeSystem("qsub -l mem=8gb,walltime=2:00:00 -W depend=afterok:$pstep_jobs -v j=$i -N $set-ph4b-$i $log_n_notify $ph4b_scr >& $scrptDir/$set.phase4b.$i.log");
        $idx = getJobId("$scrptDir/$set.phase4b.$i.log");
        push @idx_submitted, $idx;
	    print "$i : $idx\n";
    }
}


# Create the config & glue files and MERT script for tuning step #
sub create_mert_files {
    print STDERR "Creating files for running MERT ...\n";
    $pstep_jobs = join(":", @last_step_jobs);
    @idx_submitted = ();

    my $pl_scrpt = dirname(abs_path($0))."/create_mert_files.pl";
    my $mert_meta_cmd = "perl $pl_scrpt $config_file $devset_split $testset_split";
    writeCmd2File($mert_meta_scr, $mert_meta_cmd);

    safeSystem("qsub -W depend=afterok:$pstep_jobs -N create-mert-files $log_n_notify $mert_meta_scr >& $mert_meta_scr.log");
    $idx = getJobId("$mert_meta_scr.log");
    push @idx_submitted, $idx;
}


# Delete temporary files of the previous steps #
sub delTempFiles {
    print STDERR "submitting jobs for deleting temp files:\n";
    my $i;
    $pstep_jobs = join(":", @idx_submitted);

    my @del_cmds = ();
    push @del_cmds, "/bin/rm -rf $rules_dir/devset-temp/" if (defined $cfg->{DEV_DIR});
    push @del_cmds, "/bin/rm -rf $rules_dir/testset-temp/" if (defined $cfg->{TEST_DIR});
    push @del_cmds, "/bin/rm $scrptDir/*";
    push @del_cmds, "/bin/rm $logDir/*";
    push @del_cmds, "unlink $model_root/$del_scr";
    writeCmd2File($del_scr, @del_cmds);

    safeSystem("qsub -W depend=afterok:$pstep_jobs -e /dev/null -o /dev/null $del_scr");
}


sub writeCmd2File {
    my $script_file = shift;
    my @cmds = @_;
    my $cmd;

    open(SF, "> $script_file");
    print SF "#! /bin/tcsh \n\n";
    ## Specify stuffs such as loading particular modules as required for your cluster
    #print SF "source /cs/natlang-sw/etc/natlang-login \n";
    #print SF "module load NL/LANG/PYTHON/2.6.2 \n\n";

    for $cmd (@cmds) { print SF "$cmd\n"; }

    #print SF "\nmodule unload NL/LANG/PYTHON/2.6.2 \n";
    print SF "rm -rf /local-scratch/\${PBS_JOBID}\n";
    close(SF);

    # Set execute permission for the script
    chmod(oct(755), $script_file);
}


sub getJobId {
    # Get the job-id from the log file
    my $log_file = shift;

    my $line = "";
    my $id;

    open(LF, $log_file) || die "Log file $log_file doesn't exists! Exiting";
    chomp($line=<LF>);
    ($id,) = split(/\./, $line);
    close(LF);

    return int($id);
}


sub safeSystem {
    print "   * About to Execute : @_\n";
    system(@_);
    #if ($? != 0) { die "$? ::Failed executing [@_]\n"; }

    if ($? == -1) {
        print STDERR "Failed to execute: @_\n  $!\n";
        exit 1;
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

