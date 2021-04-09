library(tidyverse)
library(ggpubr)

files_ref_to_int = c("/Users/jwinnikoff/Documents/MBARI/spectackler/20210106_t-cal_DallasVsInternal.tsv")
files_ext_to_ref = c("/Users/jwinnikoff/Documents/MBARI/spectackler/20210112_t-cal_baseRTD1.tsv", "/Users/jwinnikoff/Documents/MBARI/spectackler/20210112_t-cal_baseRTD2.tsv")

ref_to_int <- files_ref_to_int %>%
  lapply(read_tsv) %>%
  bind_rows() %>%
  pivot_longer(cols = c("T_int", "T_ext", "T_ref"), names_to = "sensor", values_to = "temp") %>%
  rowwise() %>%
  # crop time domain
  filter(watch >= 1500 && watch <= 18500) %>%
  group_by(sensor) %>%
  filter(sensor != "T_ext") %>%
  arrange(clock) %>%
  mutate(dir = ifelse(temp > lag(temp), "up", "dn"))

# plot raw traces
ref_to_int %>%
  ggplot(aes(x=watch, y=temp, color=sensor)) +
  geom_point(size=0.5) +
  theme_pubr()

# plot correlations
ref_to_int %>%
  pivot_wider(names_from = "sensor", values_from = "temp") %>%
  ggplot(aes(y=T_int, x=T_ref, color=dir)) +
  geom_point(size=0.5, alpha = 0.2) +
  geom_smooth(method="lm", size=0.2) +
  theme_pubr()

ext_to_ref <- files_ext_to_ref %>%
  lapply(read_tsv) %>%
  bind_rows() %>%
  pivot_longer(cols = c("T_int", "T_ext", "T_ref"), names_to = "sensor", values_to = "temp") %>%
  rowwise() %>%
  # drop sensor failures
  filter(temp > 1 && temp < 40) %>%
  # crop time domain
  filter(watch >= 5000 && watch <= 14000) %>%
  group_by(sensor) %>%
  filter(sensor != "T_int") %>%
  arrange(clock) %>%
  mutate(dir = ifelse(temp > lag(temp), "up", "dn"))

# plot raw traces
ext_to_ref %>%
  ggplot(aes(x=watch, y=temp, color=sensor)) +
  geom_point(size=0.5) +
  theme_pubr()

# plot correlations
ext_to_ref %>%
  pivot_wider(names_from = "sensor", values_from = "temp") %>%
  ggplot(aes(y=T_ref, x=T_ext, color=dir)) +
  geom_point(size=0.5, alpha = 0.2) +
  geom_smooth(method="lm", size=0.2) +
  theme_pubr()

# now run the lms explicitly
coeffs_ref_to_int <- ref_to_int %>%
  pivot_wider(names_from = "sensor", values_from = "temp") %>%
  filter(!is.na(dir)) %>%
  group_by(dir) %>%
  group_split() %>%
  lapply(function(data){lm(formula = T_int ~ T_ref, data)}) %>%
  lapply(function(fit){fit$coefficients})

coeffs_ext_to_ref <- ext_to_ref %>%
  pivot_wider(names_from = "sensor", values_from = "temp") %>%
  filter(!is.na(dir)) %>%
  group_by(dir) %>%
  group_split() %>%
  lapply(function(data){lm(formula = T_ref ~ T_ext, data)}) %>%
  lapply(function(fit){fit$coefficients})

# average the ascending and descending coefficients
coef_ref_to_int <- coeffs_ref_to_int %>%
  setNames(seq(2)) %>%
  as_tibble() %>% t() %>% as_tibble() %>%
  set_colnames(c("xcept", "slope")) %>%
  summarize_all(mean)

coef_ext_to_ref <- coeffs_ext_to_ref %>%
  setNames(seq(2)) %>%
  as_tibble() %>% t() %>% as_tibble() %>%
  set_colnames(c("xcept", "slope")) %>%
  summarize_all(mean)

# link the calibrations to each other (form y = A * x + B)
# T_act = Aref2int * (Aext2ref * T_ext + Bext2ref) + Bref2int
#   "   = (Aref2int * Aext2ref) * T_ext + (Aref2int * Bext2ref + Bref2int)
# the internal RTD is traceable, so ext_to_int = ext_to_act
slope_ext_to_int = coef_ref_to_int$slope * coef_ext_to_ref$slope
xcept_ext_to_int = (coef_ref_to_int$slope * coef_ext_to_ref$xcept) + coef_ref_to_int$xcept

# what's that curve look like?
c(0,30) %>%
  tibble() %>%
  ggplot(aes(x=`.`, y=`.`)) +
  geom_point() +
  geom_abline(slope=slope_ext_to_int, intercept=xcept_ext_to_int) +
  theme_pubr() +
  labs(x="External RTD", y="Actual Temp")
