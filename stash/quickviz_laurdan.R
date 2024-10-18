library(tidyverse)
library(ggpubr)
library(gridExtra)
library(MBA)
library(reshape2)

dir_data <- "~/Documents/MBARI/Lipids/CubetteData"

files_data <- list.files(path = dir_data, pattern = "tsv", full.names = T)

fluordata <- files_data %>%
  lapply(
    function(file_data){
      data_this_file <- file_data %>%
        read_tsv() %>%
        mutate(run = file_data %>% basename())
      return(data_this_file)
    }
  ) %>%
  do.call(rbind, .)

# just averages the ~5 consecutive readings
fluordata_avgd <- fluordata %>%
  filter(abs(P_act - P_set) < 1) %>%
  filter(intensity > 30) %>%
  group_by(P_set, T_set, wl_em, state, run) %>%
  summarize(
    intensity = mean(intensity),
    watch = mean(watch),
    T_act = mean(T_act),
    P_act = mean(P_act)
    )

# effective spread that makes sure 440/490 msmts are properly paired
fluordata_440 <- fluordata_avgd %>%
  filter(wl_em == 440) %>%
  mutate(state_match = state)

fluordata_490 <- fluordata_avgd %>%
  filter(wl_em == 490) %>%
  mutate(state_match = state-1)

gpdata <- fluordata_440 %>%
  left_join(fluordata_490, by=c("T_set", "P_set", "state_match"), suffix=c("_440", "_490")) %>%
  drop_na() %>%
  mutate(
    gp = (intensity_440-intensity_490)/(intensity_440+intensity_490),
    T_act = mean(T_act_440, T_act_490),
    P_act = mean(P_act_440, P_act_490)
    ) %>%
    # drop outliers
    group_by(T_set) %>%
    filter(between(gp, mean(gp, na.rm=TRUE) - (2.5 * sd(gp, na.rm=TRUE)),
                       mean(gp, na.rm=TRUE) + (2.5 * sd(gp, na.rm=TRUE))))

var_n_lab <- c(
  "temp" = c("T_act", "Temperature (deg C)"),
  "pres" = c("P_act", "Pressure (bar)"),
  "gp" = c("gp", "Laurdan GP")
)

plots <- c()

breaklist <- gpdata %>%
  pull(gp) %>%
  {seq(from=min(.), to=max(.), length.out = 10)} %>%
  c(., 2*.[length(.)] - .[length(.)-1])

# color=GP
plots[[1]] <- gpdata %>%
  ungroup() %>%
  select(T_act, P_act, gp) %>%
  # interpolate!
  mba.surf(no.X=100, no.Y=100, extend=TRUE) %>%
  .$xyz.est %>%
  reshape2::melt(.$z, varnames = c('T_act', 'P_act'), value.name = 'gp') %>%
  as.tibble() %>%
  # rescale
  mutate(P_act = 5*P_act, T_act = T_act/4) %>%
  filter((P_act >= 0) & (T_act >= 0)) %>%
  ggplot(aes_string(x=var_n_lab[["temp1"]], y=var_n_lab[["pres1"]], z=var_n_lab[["gp1"]], fill=var_n_lab[["gp1"]])) +
  geom_raster() +
  geom_contour(color="grey", bins=10) +
  scale_fill_distiller(palette="YlGnBu") +
  geom_point(data = gpdata, color = "black", alpha=0.2, shape=1) +
  theme_pubr() +
  theme(legend.position = "bottom") +
  scale_y_reverse() +
  ggtitle("GP vs. Pressure vs. Temperature") +
  labs(x=var_n_lab[["temp2"]], y=var_n_lab[["pres2"]], fill=var_n_lab[["gp2"]]) +
  guides(fill = guide_colourbar(label.theme = element_text(angle = 45, vjust=0.5)))

# color=press
plots[[2]] <- gpdata %>%
  ggplot(aes_string(x=var_n_lab[["temp1"]], var_n_lab[["gp1"]], color=var_n_lab[["pres1"]])) +
  geom_point(alpha=0.4) +
  theme_pubr() +
  theme(legend.position = "bottom") +
  scale_color_distiller(palette="PuRd", direction=1) +
  ggtitle("Pressure vs. GP vs. Temperature") +
  labs(x=var_n_lab[["temp2"]], y=var_n_lab[["gp2"]], color=var_n_lab[["pres2"]]) +
  guides(color = guide_colourbar(label.theme = element_text(angle = 45, vjust=0.5)))

# color=temp
plots[[3]] <- gpdata %>%
  ggplot(aes_string(x=var_n_lab[["pres1"]], var_n_lab[["gp1"]], color=var_n_lab[["temp1"]])) +
  geom_point(alpha=0.4) +
  theme_pubr() +
  theme(legend.position = "bottom") +
  scale_color_distiller(palette="YlOrRd", direction=1) +
  ggtitle("Temperature vs. GP vs. Pressure") +
  labs(x=var_n_lab[["pres2"]], y=var_n_lab[["gp2"]], color=var_n_lab[["temp2"]]) +
  guides(color = guide_colourbar(label.theme = element_text(angle = 45, vjust=0.5)))

grid.arrange(plots[[1]], plots[[2]], plots[[3]], nrow = 1)

# without the namedlist
gpdata %>%
  ggplot(aes(x=T_act, y=P_act, color=gp)) +
    geom_point(alpha=0.4) +
    theme_pubr() +
    theme(legend.position = "right") +
    scale_color_distiller(palette="YlGnBu") +
    scale_y_reverse() +
    ggtitle("GP vs. pressure vs. temperature (1/100 Dr. Bronner's)") +
    labs(x="Temperature (deg C)", y="Pressure (bar)", color="Laurdan GP")

# for messy data (incorrect WLs/states)
cleandata <- fluordata %>%
  filter(abs(P_act - P_set) < 1) %>%
  filter(intensity > 30) %>%
  mutate(wl_em = ifelse(intensity > 100, 490, 440)) %>%
  mutate(direction = ifelse(state > max(state)/2, "up", "down")) %>%
  filter(((wl_em == 440) & (lead(wl_em) == 490)) | ((wl_em == 490) & (lag(wl_em) == 440)))

gpdata <- cleandata %>%
  group_by(P_set, state, direction, run) %>%
  arrange(state, wl_em) %>%
  summarize(gp = (first(intensity)-last(intensity))/(first(intensity)+last(intensity)))
  #summarize(gp = (`440`-`490`)/(`440`+`490`))

gpdata %>%
  filter(gp < -0.4) %>%
  filter((run != "20200719_viscotest4.tsv") | (direction == "down")) %>%
  ggplot(aes(x=P_set, y=gp, color=direction, shape=run)) +
  geom_point(alpha = 0.5) +
  theme_pubr() +
  scale_color_brewer(palette="Dark2") +
  ggtitle("GP vs. pressure (1/100 Dr. Bronner's @ 25˚C)") +
  xlab("Pressure (bar)") +
  ylab("Laurdan GP") +
  theme(legend.position="bottom", legend.box="vertical")

# time plot
fluordata %>%
  filter(abs(P_act - P_set) < 1) %>%
  filter(intensity > 30) %>%
  ggplot(aes(x=watch, y=intensity, color=factor(state%%2))) +
    geom_point(alpha=0.4) +
    theme_pubr() +
    guide_legend(override.aes = color)
