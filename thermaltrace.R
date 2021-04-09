# display the end of a real-time thermal trace

library(tidyverse)
library(ggpubr)
library(gridExtra)

file_data <- "/Applications/spectackler/20210112_topside_tempscan.tsv"

# get the last n lines of data
n_lines <- 5000

linecount <- function(target_file){
  system2("wc",
    args = c("-l",
      target_file,
      " | awk '{print $1}'"),
    stdout = TRUE
  ) %>% 
    as.integer()
}

while (TRUE){
  numlines <- linecount(file_data)
  
  #print(numlines - n_lines)
  data <- file_data %>% 
    read_tsv(skip = max(2, numlines - n_lines), col_names=FALSE) %>% 
    setNames(c("t", "T_set", "T_int", "T_ext", "P", "I", "D", "Kp", "Ki", "Kd"))
  
  plotPV <- data %>% 
    mutate_all(as.numeric) %>% 
    pivot_longer(cols=c("T_set", "T_int", "T_ext"), names_to="sensor", values_to="temp") %>% 
    ggplot(aes(x=(t-first(t))/60, y=temp, color=sensor)) +
      geom_line() +
      theme_pubr()
  
  plotPID <- data %>% 
    mutate_all(as.numeric) %>% 
    pivot_longer(cols=c("P", "I", "D"), names_to="component", values_to="val") %>% 
    ggplot(aes(x=(t-first(t))/60, y=val, color=component)) +
    geom_line() +
    theme_pubr()
  
  print(grid.arrange(plotPV, plotPID, nrow = 2))
  
  Sys.sleep(30)
  dev.off()
}
