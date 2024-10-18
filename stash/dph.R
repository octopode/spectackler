# this script loads a DPH anisotropy run and plots landscapes

library(tidyverse)
library(ggpubr)
library(gridExtra)
library(MBA)
library(reshape2)

# where the data comes from
#dir_data <- "/Users/jwinnikoff/Documents/MBARI/Lipids/CubetteData/20210115_dph_full"
dir_data <- "/Volumes/spectackler"
pat_data <- "*20210221_DOPC_DPH*" # filename pattern

# how we tell whether shutter is open
thres_intens <- 2

# read in raw data
readin <- function(dir, pat){
  files_data <- list.files(path = dir, pattern = pat, full.names = T)

  files_data %>%
    lapply(
      function(file_data){
        data_this_file <- file_data %>%
          read_tsv() %>%
          mutate(file = file_data %>% basename())
        return(data_this_file)
      }
    ) %>%
    do.call(rbind, .)
}

raw2aniso <- function(rawdata, thres_intens){
  # calc baseline
  baseline <- rawdata %>%
    filter(intensity < thres_intens) %>%
    pull(intensity) %>%
    mean()
  # work up data
  rawdata %>%
    rowwise() %>%
    # discard closed-shutter data
    filter(intensity >= thres_intens) %>%
    # discard filters-off data
    filter(!('None' %in% c(pol_ex, pol_em))) %>%
    # baseline-adjust
    mutate(intensity = intensity - baseline) %>%
    # group data for each state
    group_by(pol_ex, pol_em) %>%
    mutate(pol = paste(pol_ex, pol_em, sep='')) %>%
    group_by(P_set, T_set, pol, msg) %>%
    # just the last 15 values
    arrange(watch) %>%
    do(tail(., n=15)) %>%
    group_by(P_set, T_set, msg) %>%
    mutate(
      P_act = mean(P_act),
      T_act = mean(T_act)
    ) %>%
    group_by(P_set, T_set, P_act, T_act, pol, msg) %>% #ggplot(aes(x=watch, y=intensity)) + geom_point(alpha=0.1)
    # remove 2-sigma outliers (spurious readings)
    filter(abs(intensity - mean(intensity)) <= 2*sd(intensity)) %>%
    #ggplot(aes(x=watch, y=intensity, color=msg)) + geom_point() + geom_line(aes(y=T_act), color="red")
    summarize(intensity = mean(intensity)) %>%
    pivot_wider(names_from = "pol", values_from = "intensity") %>%
    mutate(
      # calc G-factors
      g = HV/HH,
      # calc aniso values
      r = (VV - (g*VH)) / (VV + (2*g*VH))
    )# %>% pull(g) %>% qplot(binwidth = 0.01) + theme_pubr() + labs(x="G", y="count")
}

# thru time
rawdata %>%
  filter(
    intensity > 1 &
      intensity < 7.5
  ) %>%
  filter(pol_ex == 'H') %>%
  ggplot(aes(x=watch, y=intensity)) +
  geom_point(alpha=0.2) +
  theme_pubr()

# read in
rawdata <- readin(dir_data, pat_data)
# reduce to aniso values
anisodata <- rawdata %>% raw2aniso(thres_intens = thres_intens)

rawdata %>% pull(intensity) %>% qplot(binwidth=0.05)

contourplot(anisodata, nox=100, noy=100){
  anisodata_clean <- anisodata %>%
    #can compare the up- vs. downcast this way
    rowwise() %>% filter(str_detect(msg, "dir:tdn")) %>%
    filter(!is.na(r))
  anisodata_clean %>%
    ungroup() %>%
    select(T_act, P_act, r) %>%
    # interpolate!
    mba.surf(no.X=nox, no.Y=noy, extend=TRUE) %>%
    .$xyz.est %>%
    reshape2::melt(.$z, varnames = c('T_act_sc', 'P_act_sc'), value.name = 'r') %>%
    as_tibble() %>%
    drop_na() %>%
    # rescale
    mutate(
      P_act = P_act_sc/noy * (max(anisodata_clean$P_act)-min(anisodata_clean$P_act)) + min(anisodata_clean$P_act),
      T_act = T_act_sc/nox * (max(anisodata_clean$T_act)-min(anisodata_clean$T_act)) + min(anisodata_clean$T_act)
    ) %>%
    ggplot(aes(x=T_act, y=P_act, color=-r, z=r)) +
    geom_contour_filled(bins=9) +
    geom_point(data = anisodata_clean, size=3, alpha=0.15) +
    geom_point(data = anisodata_clean, size=3, shape=1, color="black", alpha=0.15) +
    scale_y_reverse() +
    scale_color_distiller(palette = "YlGnBu") +
    scale_fill_brewer(palette = "YlGnBu") +
    theme_pubr() +
    theme(legend.position="right")
}



%>%
  ggplot(aes(x=factor(T_set), y=g, fill=factor(T_set))) + geom_violin(size=0) + geom_point(size=3, alpha=0.3)
# can compare the up- vs. downcast this way
#rowwise() %>% filter(str_detect(msg, "tup")) %>%
anisodata %>%
ggplot(aes(x=T_act, y=P_act, color=r, z=r)) + geom_point(size=3, alpha=0.3) + geom_contour(aes(color=after_stat(level)))
