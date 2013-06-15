package TrainConfig;

use File::Basename;

sub new {
    my($class, $cfg_file) = @_;
    $self->{config_file} = $cfg_file;
    bless($self, $class);
    $self->load_config();
    $self->set_defaults();
    return $self;
}

sub load_config {
    my($self) = @_;
    my $key;
    my $val;
    my $lc_key;
    my $step;
    my @steps = ();

    print "Loading the training config file : $self->{config_file} ...\n";
    open(CFG, $self->{config_file});
    while(<CFG>) {
        chomp;
        s/(^\s+|\s+$)//g;
        next if ($_ =~ /^#/ || $_ =~ /^$/);

        ($key, $val) = split(/=/);
        $key =~ s/(^\s+|\s+$)//g;
        $val =~ s/(^\s+|\s+$)//g;

        if ($key =~ /KRIYA_MODELS/) { $val =~ s/\/$//; }
        elsif ($key =~ /(TRAIN|DEV|TEST)_DIR/) {
            $val =~ s/\/$//;
            $step = $key;
            $step =~ s/_DIR//;
            push(@steps, $step);
            if (!-e $val || !-d $val) { die "ERROR: Parameter $key has the path $val\n\tEither the path doesn't exist or is not a directory. Exiting!\n"; }
            $lc_key = "LC_".$key;
            $lc_val = $self->get_lc_dirs($val);
            $self->{$lc_key} = $lc_val;
            print "$lc_key * $lc_val\n";
        }
        $self->{$key} = $val;
    }
    if (@steps) { $self->{STEPS} = join(',', sort(@steps)); }
    else { die "ERROR: Specify at least one step by defining one of TRAIN_DIR, DEV_DIR and TEST_DIR. Exiting!\n"; }
}1;

sub get_lc_dirs {
    my($self, $data_dir) = @_;
    my($d_name, $path) = fileparse($data_dir);
    return $self->{KRIYA_MODELS}."/training/pre-processed/lc-".$d_name;
}

sub set_defaults {
    my($self) = @_;
    if (!defined $self->{max_sent_len}) { $self->set_n_log("max_sent_len", 80); }
    if (!defined $self->{max_phr_len}) { $self->set_n_log("max_phr_len", 10); }
    if (!defined $self->{giza_parts}) { $self->set_n_log("giza_parts", 5); }
    if (!defined $self->{first_step}) { $self->set_n_log("first_step", 1); }
    if (!defined $self->{last_step}) { $self->set_n_log("last_step", 5); }
    if (!defined $self->{fr_side_len}) { $self->set_n_log("fr_side_len", 5); }
    if (!defined $self->{non_terminals}) { $self->set_n_log("non_terminals", 2); }
    if (!defined $self->{split_size}) { $self->set_n_log("split_size", 10000); }
    if (!defined $self->{sent_per_file}) { $self->set_n_log("sent_per_file", 200); }
    if (!defined $self->{shallow_hiero}) { $self->set_n_log("shallow_hiero", False); }
    if (!defined $self->{use_srilm}) { $self->set_n_log("use_srilm", False); }
    if (!defined $self->{cbp}) { $self->set_n_log("cbp", 500); }
    if (!defined $self->{lm_order}) { $self->set_n_log("lm_order", 5); }
    if (!defined $self->{nbest_size}) { $self->set_n_log("nbest_size", 100); }
    if (!defined $self->{nbest_format}) { $self->set_n_log("nbest_format", True); }
    if (!defined $self->{optimizer}) { $self->set_n_log("optimizer", "pro"); }
    if (!defined $self->{opt_metric}) { $self->set_n_log("opt_metric", "bleu"); }
    if (!defined $self->{opt_sampler}) { $self->set_n_log("opt_sampler", "rank"); }
    #if (!defined $self->{}) { $self->set_n_log("", ); }
}

sub set_n_log {
    my($self, $key, $val) = @_;
    $self->{$key} = $val;
    print STDERR "INFO: Parameter $key is undefined. Using the default value: $val\n";
}

