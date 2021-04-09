# script for visualizing Laurdan GP landscapes (in real time, if desired!)

library(tidyverse)
library(ggpubr)
library(gridExtra)
library(MBA)
library(reshape2)

dir_data <- "/Users/cubette/Data/"
pat_data <- "*20210226_JWL0087P_laurdan_*" # filename pattern

# how we tell whether shutter is open
thres_intens <- 10

# live plotting loop
refresh = 5 # (seconds)
img_out = "~/Data/20210226_JWL0087P_laurdan_340.pdf"

while(TRUE){
  time_start <- Sys.time()
  
  # read in data
  rawdata <- readin(dir_data, pat_data)
  # reduce to GP
  gpdata  <- raw2gp(rawdata, thres_intens = thres_intens)
  
  # plot Cubette state
  plot_pt <- stateplot(rawdata, lims_t = range(rawdata$T_act), lims_p = range(rawdata$P_act)) + ggtitle("Cubette State")
  # plot GP
  plot_gp <- contourplot(gpdata, lims_t = range(rawdata$T_act), lims_p = range(rawdata$P_act), gpmin=-0.1, gpmax=0.4) + ggtitle("GP vs. Pressure vs. Temperature")
  
  image <- arrangeGrob(plot_pt, plot_gp, ncol=1, heights=c(1,2))
  ggsave(file = img_out, plot = image, width = 6.5, height = 8.0)
  
  time_sleep = max(0, refresh - (Sys.time() - time_start))
  Sys.sleep(time_sleep)
}

## HELPER FUNCTIONS
# read in raw data
readin <- function(dir, pat){
  files_data <- list.files(path = dir, pattern = pat, full.names = T)
  print(files_data)
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

raw2gp <- function(rawdata, thres_intens){
  # calc baseline
  baseline <- rawdata %>%
    filter(intensity < thres_intens) %>%
    pull(intensity) %>%
    mean()
  # work up data
  rawdata %>%
    rowwise() %>%
    filter(
      # discard closed-shutter data
      (intensity >= thres_intens) &
        # and wrong-WL data
        (wl_ex == 340) &
        (wl_em %in% c(440, 490))
    ) %>%
    # baseline-adjust
    mutate(intensity = intensity - baseline) %>%
    # group data for each state
    group_by(P_set, T_set, wl_ex, wl_em, msg) %>%
    # just the last 10 values
    group_by(state, n_read) %>% 
    top_n(n_read-1, desc(watch)) %>%
    group_by(P_set, T_set, msg) %>%
    mutate(
      P_act = mean(P_act),
      T_act = mean(T_act)
    ) %>%
    group_by(P_set, T_set, P_act, T_act, wl_ex, wl_em, msg) %>% #ggplot(aes(x=watch, y=intensity)) + geom_point(alpha=0.1)
    # remove 2-sigma outliers (spurious readings)
    filter(abs(intensity - mean(intensity)) <= 2*sd(intensity)) %>%
    summarize(intensity = mean(intensity)) %>%
    pivot_wider(names_from = "wl_em", values_from = "intensity") %>%
    # calc GP
    mutate(gp = (`440` - `490`)/(`440` + `490`))
}

# fixed-scale contour plot of GP data
contourplot <- function(gpdata, nox=100, noy=100, binwidth=0.05, gpmin=-0.1, gpmax=0.4, lims_t=c(3,28), lims_p=c(0,500)){
  gpdata_clean <- gpdata %>%
    #can compare the up- vs. downcast this way
    rowwise() %>% 
      #filter(!str_detect(msg, "rep:0")) %>%
      filter(!is.na(gp))
  
  gpdata_clean %>%
    ungroup() %>%
    select(T_act, P_act, gp) %>%
    # interpolate!
    mba.surf(no.X=nox, no.Y=noy, extend=TRUE) %>%
    .$xyz.est %>%
    reshape2::melt(.$z, varnames = c('T_act_sc', 'P_act_sc'), value.name = 'gp') %>%
    as_tibble() %>%
    drop_na() %>%
    # rescale
    mutate(
      P_act = P_act_sc/noy * (max(gpdata_clean$P_act)-min(gpdata_clean$P_act)) + min(gpdata_clean$P_act),
      T_act = T_act_sc/nox * (max(gpdata_clean$T_act)-min(gpdata_clean$T_act)) + min(gpdata_clean$T_act)
    ) %>%
    ggplot(aes(x=T_act, y=P_act, color=gp, z=gp)) +
    geom_contour_filled(aes(fill=stat(level_mid)), binwidth=binwidth) +
    geom_point(data = gpdata_clean, size=3, alpha=0.15) +
    geom_point(data = gpdata_clean, size=3, shape=1, color="black", alpha=0.15) +
    scale_y_reverse() +
    scale_color_distiller(palette = "YlGnBu", direction=+1, limits=c(gpmin, gpmax)) +
    scale_fill_distiller(palette = "YlGnBu", direction=+1, limits=c(gpmin, gpmax)) +
    theme_pubr() +
    theme(legend.position="bottom") +
    guides(
      fill = "none",
      color = guide_colourbar(label.theme = element_text(angle = 45, vjust=0.5))
    ) +
    labs(
      x = "Temperature (deg C)",
      y = "Pressure (bar)",
      color = "Laurdan GP "
    ) +
    lims(x=lims_t)
}

stateplot <- function(rawdata, lims_t=c(3,28), lims_p=c(0,500)){
  rawdata %>% 
    select(clock, T_act, P_act) %>% 
    arrange(clock) %>% 
    mutate(age = difftime(last(clock), clock, units = "sec") %>% as.numeric()) %>% 
    ggplot(aes(x = T_act, y = P_act, color = age)) +
    geom_point(alpha = 0.017) +
    # highlight the last 10 minutes of data
    scale_color_gradient(low="red", high="black", na.value = "black", limits = c(0, 600)) +
    theme_pubr() +
    theme(legend.position = "none") +
    labs(x="Temperature (deg C)", y="Pressure (bar)") +
    lims(x=lims_t) +
    scale_y_reverse()
}
