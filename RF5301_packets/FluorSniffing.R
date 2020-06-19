library(tidyverse)
library(broman)
library(ggplot2)

capture <- read_table("/Users/jwinnikoff/Downloads/RF5301_packets/20200225_Scan_ex370_em400-550.tsv")

raw_hex <- capture %>% 
  pull(`ASCII`) %>% 
  paste(collapse = "") %>% 
  str_extract_all(pattern = "\\w\\w\\w\\w\\w\\w") %>% # get all 6-char words
  unlist()

raw_hex %>% 
  strtoi(base = 32L)
