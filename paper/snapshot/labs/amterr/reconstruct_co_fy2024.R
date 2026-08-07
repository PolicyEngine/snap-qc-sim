# FY2024-only adaptation of Giannella & Molin's raw-variable reconstruction
# (snap_qc repo, 1_data_munging_..._public_qc_data.R), for the Axiom AMTERR
# replay. Deviations from the original, all deliberate:
#   - loads FY2024 only; no mining stages (ranger/yardstick/ggplot2 stripped)
#   - apply_correction_smoothing = FALSE: smoothing rescales values toward
#     group means to fix at-max mining artifacts; replay needs the solver's
#     per-case solution. at_max is exported instead so weakly-identified
#     cases (benefit capped) can be flagged downstream.
#   - keeps ALL solver/filter logic verbatim otherwise.
suppressPackageStartupMessages({library(haven); library(dplyr); library(tidyr)})

repo <- Sys.getenv("SNAP_QC_REPO", "~/snap_qc/")  # clone of github.com/giannella/snap_qc
out_dir <- "/Users/maxghenis/.cache/axiom-oracles/amterr-lab/"
correct_variables <- TRUE

mydata <- read_sav(paste0(repo, "qc_data/qc_pub_fy2024.sav"))
mydata$year <- as.integer(substr(mydata$YRMONTH, 1, 4))
mydata$month <- as.integer(substr(mydata$YRMONTH, 5, 6))
mydata$fiscal_year <- ifelse(mydata$month >= 10, mydata$year + 1, mydata$year)
state_data <- read.csv(fileEncoding = "UTF-8-BOM", paste0(repo, "additional_data/state_data.csv"))
fips_to_state <- setNames(state_data$state, as.character(state_data$fips))
mydata$state_name <- fips_to_state[as.character(mydata$STATE)]
cat("loaded:", nrow(mydata), "rows\n")

mydata$absbendiff <- abs(mydata$RAWBEN - mydata$FSBEN)
mydata <- mydata[abs(mydata$absbendiff - mydata$AMTERR) <= 5, ]
ded_na_fields <- c("FSDEPDED", "FSMEDDED", "FSCSDED", "FSSTDDED", "HOMELESS_DED")
mydata$ded_fields_imputed <- rowSums(is.na(mydata[ded_na_fields])) > 0
for (v in ded_na_fields) mydata[[v]][is.na(mydata[[v]])] <- 0
mydata <- mydata %>% filter(!is.na(RENT), !is.na(UTIL))
mydata$second_element_i <- !is.na(mydata$ELEMENT2)
cat("after consistency filters:", nrow(mydata), "rows\n")

year_data <- read.csv(fileEncoding = "UTF-8-BOM", paste0(repo, "additional_data/year_data.csv"))
threshold_by_year <- setNames(year_data$error_threshold, as.character(year_data$year))
mydata$threshold <- threshold_by_year[as.character(mydata$fiscal_year)]
mydata$over_threshold <- as.factor(ifelse(mydata$absbendiff > mydata$threshold, 1, 0))
max_shelter_by_year <- setNames(year_data$max_shelter_deduction, as.character(year_data$year))
mydata$max_shelter_deduction <- ifelse(mydata$FSNELDER + mydata$FSNDIS > 0, Inf,
                                       max_shelter_by_year[as.character(mydata$fiscal_year)])
mydata$fsminimum_ben <- ifelse(mydata$FSUSIZE < 3, mydata$MINIMUM_BEN, 0)

# Step 4 (verbatim from the original): recreate FSBEN from the FS* inputs;
# the solvers use fsben_uncapped for shift direction.
mydata$fsnet_before_shelter <- mydata$FSGRINC - (mydata$FSERNDED + mydata$FSDEPDED +
  mydata$FSMEDDED + mydata$FSCSDED + mydata$FSSTDDED)
mydata$fsnet_adjusted_half <- pmax(mydata$fsnet_before_shelter * 0.5, 0)
mydata$fssltded_uncapped <- mydata$RENT + mydata$UTIL - mydata$fsnet_adjusted_half
mydata$fssltded_recalculated <- ifelse(is.infinite(mydata$max_shelter_deduction),
  pmax(mydata$fssltded_uncapped, 0),
  pmin(pmax(mydata$fssltded_uncapped, 0), mydata$max_shelter_deduction))
mydata$fsnet_allow_negative <- floor(mydata$fsnet_before_shelter -
  (mydata$fssltded_recalculated + mydata$HOMELESS_DED))
mydata$fsben_uncapped <- floor(mydata$BENMAX - (0.3 * mydata$fsnet_allow_negative))
mydata$fsben_recreated <- pmin(pmax(mydata$fsben_uncapped, mydata$fsminimum_ben), mydata$BENMAX)
cat("fsben recreated == FSBEN:", round(mean(mydata$fsben_recreated == mydata$FSBEN, na.rm = TRUE) * 100, 2), "%\n")

vars <- c("FSUSIZE","FSGRINC","FSEARN","FSUNEARN","FSERNDED","FSMEDDED","FSDEPDED",
          "FSCSDED","FSSLTDED","FSSLTEXP","RENT","UTIL","FSSTDDED","HOMELESS_DED",
          "BENMAX","MINIMUM_BEN")
for (v in vars) {
  newname <- paste0("raw", tolower(sub("^FS", "", v)))
  mydata[[newname]] <- ifelse(is.na(mydata[[v]]), 0, mydata[[v]])
}

calculate_raw_benefits <- function(mydata) {
  mydata$rawernded <- mydata$rawearn * 0.2
  mydata$rawgrinc <- mydata$rawearn + mydata$rawunearn
  mydata$rawnet_before_shelter <- mydata$rawgrinc - (mydata$rawernded + mydata$rawdepded +
    mydata$rawmedded + mydata$rawcsded + mydata$rawstdded)
  mydata$rawnet_adjusted_half <- pmax(mydata$rawnet_before_shelter * 0.5, 0)
  mydata$rawsltexp <- mydata$rawrent + mydata$rawutil
  mydata$rawsltded_uncapped <- floor(mydata$rawsltexp - mydata$rawnet_adjusted_half)
  mydata$rawsltded <- ifelse(is.infinite(mydata$max_shelter_deduction),
                             pmax(mydata$rawsltded_uncapped, 0),
                             pmin(pmax(mydata$rawsltded_uncapped, 0), mydata$max_shelter_deduction))
  mydata$rawsltded <- floor(mydata$rawsltded)
  mydata$rawnet_allow_negative <- floor(mydata$rawnet_before_shelter -
                                        (mydata$rawsltded + mydata$rawhomeless_ded))
  mydata$rawben_uncapped <- floor(mydata$rawbenmax - (0.3 * mydata$rawnet_allow_negative))
  mydata$rawben_recreated <- pmin(pmax(mydata$rawben_uncapped, mydata$rawminimum_ben), mydata$rawbenmax)
  mydata$rawnet_capped <- pmax(mydata$rawnet_allow_negative, 0)
  mydata$unc_rawben_rel_max <- mydata$rawben_uncapped / mydata$rawbenmax
  mydata$at_max <- (mydata$rawben_uncapped + 5) >= mydata$rawbenmax
  mydata
}

mydata$correctednotes <- "no_change"
mydata$correctedamount <- 0

max_allotments <- read.csv(fileEncoding = "UTF-8-BOM", paste0(repo, "additional_data/max_allotments.csv"))
max_allotments_long <- reshape(max_allotments, varying = names(max_allotments)[-1],
  v.names = "rawbenmax", timevar = "hh_size",
  times = as.integer(gsub("X", "", names(max_allotments)[-1])), direction = "long")
max_allotments_long <- max_allotments_long[, c("year", "hh_size", "rawbenmax")]
get_max_allotment <- function(hh_size, fiscal_year) {
  r <- max_allotments_long[max_allotments_long$hh_size == hh_size &
                           max_allotments_long$year == fiscal_year, "rawbenmax"]
  if (length(r) == 0) return(NA); r
}
standard_deductions <- read.csv(fileEncoding = "UTF-8-BOM", paste0(repo, "additional_data/standard_deductions.csv"))
standard_deductions_long <- reshape(standard_deductions, varying = names(standard_deductions)[-1],
  v.names = "rawstdded", timevar = "hh_size",
  times = as.integer(gsub("X", "", names(standard_deductions)[-1])), direction = "long")
standard_deductions_long <- standard_deductions_long[, c("year", "hh_size", "rawstdded")]
get_standard_deduction <- function(hh_size, fiscal_year) {
  r <- standard_deductions_long[standard_deductions_long$hh_size == hh_size &
                                standard_deductions_long$year == fiscal_year, "rawstdded"]
  if (length(r) == 0) return(NA); r
}

if ("rawbenmax" %in% names(mydata)) mydata$rawbenmax <- NULL
mydata <- mydata %>% left_join(max_allotments_long, by = c("fiscal_year" = "year", "rawusize" = "hh_size"))
mydata <- mydata[mydata$BENMAX == mydata$rawbenmax, ]
cat("after BENMAX table check:", nrow(mydata), "rows\n")

# unit composition (element 150)
mydata$rawusize <- ifelse(mydata$ELEMENT1 == 150 & mydata$NATURE1 %in% c(12, 14, 16),
                          mydata$rawusize - 1, mydata$rawusize)
mydata$correctednotes <- ifelse(mydata$ELEMENT1 == 150 & mydata$NATURE1 %in% c(12, 14, 16),
                                "hhsize_up", mydata$correctednotes)
mydata$rawusize <- ifelse(mydata$ELEMENT1 == 150 & mydata$NATURE1 %in% c(7),
                          mydata$rawusize + 1, mydata$rawusize)
mydata$correctednotes <- ifelse(mydata$ELEMENT1 == 150 & mydata$NATURE1 %in% c(7),
                                "hhsize_down", mydata$correctednotes)
if (correct_variables) {
  mydata$rawbenmax <- mapply(get_max_allotment, hh_size = mydata$rawusize, fiscal_year = mydata$fiscal_year)
  mydata$rawstdded <- mapply(get_standard_deduction, hh_size = mydata$rawusize, fiscal_year = mydata$fiscal_year)
  mydata$rawminimum_ben <- ifelse(mydata$rawusize < 3, mydata$MINIMUM_BEN, 0)
}

income_shift <- 3
max_iterations <- 1000

adjust_income <- function(mydata, col, elements, prefix, max_iter = max_iterations) {
  eligible <- mydata$ELEMENT1 %in% elements
  original <- mydata[[col]]
  for (i in seq_len(max_iter)) {
    mydata <- calculate_raw_benefits(mydata)
    direction <- mydata$RAWBEN - mydata$fsben_uncapped
    diff <- mydata$RAWBEN - mydata$rawben_recreated
    diff_matches <- abs(diff) <= 3
    done <- ((direction > 0 & mydata[[col]] <= 0) | mydata$rawben_recreated <= 0 |
               (direction < 0 & mydata$rawben_recreated < mydata$RAWBEN) |
               (direction > 0 & mydata$rawben_recreated > mydata$RAWBEN) |
               (direction < 0 & mydata$rawben_uncapped < 0) | !eligible)
    if (all(done, na.rm = TRUE)) break
    mydata[[col]] <- ifelse(!done & direction > 0, pmax(mydata[[col]] - income_shift, 0),
                     ifelse(!done & direction < 0, mydata[[col]] + income_shift, mydata[[col]]))
  }
  changed <- mydata[[col]] != original
  hit_zero <- (direction > 0) & (mydata[[col]] <= 0 | mydata$rawben_recreated <= 0)
  mydata$correctednotes <- ifelse(
    eligible & hit_zero & !diff_matches, paste0(prefix, "_error"),
    ifelse(eligible & changed & mydata$RAWBEN > mydata$fsben_uncapped, paste0(prefix, "_down"),
    ifelse(eligible & changed & mydata$RAWBEN < mydata$fsben_uncapped, paste0(prefix, "_up"),
    ifelse(eligible, paste0(prefix, "_no_change"), mydata$correctednotes))))
  mydata$correctedamount <- ifelse(eligible, mydata[[col]] - original, mydata$correctedamount)
  mydata
}

adjust_shelter <- function(mydata, col, elements, prefix, max_iter = max_iterations) {
  eligible <- mydata$ELEMENT1 %in% elements
  original <- mydata[[col]]
  for (i in seq_len(max_iter)) {
    mydata <- calculate_raw_benefits(mydata)
    direction <- mydata$RAWBEN - mydata$FSBEN
    diff <- mydata$RAWBEN - mydata$rawben_recreated
    diff_matches <- abs(diff) <= 3
    done <- (diff_matches | (mydata[[col]] <= 0 & direction < 0) | mydata$rawben_recreated <= 0 |
               (direction > 0 & mydata$rawben_recreated > mydata$RAWBEN) |
               (direction < 0 & mydata$rawben_recreated < mydata$RAWBEN) |
               (direction > 0 & mydata$rawsltded_uncapped >= mydata$max_shelter_deduction) |
               (direction < 0 & mydata$rawsltded <= 0) | !eligible)
    if (all(done, na.rm = TRUE)) break
    mydata[[col]] <- ifelse(!done & direction < 0, pmax(mydata[[col]] - income_shift, 0),
                     ifelse(!done & direction > 0, mydata[[col]] + income_shift, mydata[[col]]))
  }
  hit_zero <- (mydata[[col]] <= 0) & !diff_matches & direction < 0
  hit_cap <- !diff_matches & direction > 0 & mydata$rawsltded >= mydata$max_shelter_deduction
  mydata$correctednotes <- ifelse(
    eligible & (hit_zero | hit_cap) & prefix != "util", paste0(prefix, "_error"),
    ifelse(eligible & direction > 0, paste0(prefix, "_up"),
    ifelse(eligible & direction < 0, paste0(prefix, "_down"),
    ifelse(eligible, paste0(prefix, "_no_change"), mydata$correctednotes))))
  mydata$correctedamount <- ifelse(eligible, mydata[[col]] - original, mydata$correctedamount)
  mydata
}

adjust_other <- function(mydata, col, elements, prefix, max_iter = max_iterations) {
  eligible <- mydata$ELEMENT1 %in% elements
  original <- mydata[[col]]
  for (i in seq_len(max_iter)) {
    mydata <- calculate_raw_benefits(mydata)
    direction <- mydata$RAWBEN - mydata$FSBEN
    diff <- mydata$RAWBEN - mydata$rawben_recreated
    diff_matches <- abs(diff) <= 3
    done <- (diff_matches | (mydata[[col]] <= 0 & direction < 0) | mydata$rawben_recreated <= 0 |
               (direction > 0 & mydata$rawben_recreated > mydata$RAWBEN) |
               (direction < 0 & mydata$rawben_recreated < mydata$RAWBEN) |
               (direction < 0 & mydata[[col]] <= 0) | !eligible)
    if (all(done, na.rm = TRUE)) break
    mydata[[col]] <- ifelse(!done & direction < 0, pmax(mydata[[col]] - income_shift, 0),
                     ifelse(!done & direction > 0, mydata[[col]] + income_shift, mydata[[col]]))
  }
  hit_zero <- (mydata[[col]] <= 0) & !diff_matches & direction < 0
  hit_cap <- !diff_matches & direction > 0
  mydata$correctednotes <- ifelse(
    eligible & (hit_zero | hit_cap), paste0(prefix, "_error"),
    ifelse(eligible & direction > 0, paste0(prefix, "_up"),
    ifelse(eligible & direction < 0, paste0(prefix, "_down"),
    ifelse(eligible, paste0(prefix, "_no_change"), mydata$correctednotes))))
  mydata$correctedamount <- ifelse(eligible, mydata[[col]] - original, mydata$correctedamount)
  mydata
}

if (correct_variables) {
  mydata <- adjust_income(mydata, "rawunearn", c(331,332,333,334,335,336,342,343,344,345,346,350), "unearn")
  mydata <- adjust_income(mydata, "rawearn", c(311,312,314,321), "earn")
  mydata <- adjust_shelter(mydata, "rawrent", c(363), "rent")
  mydata <- adjust_shelter(mydata, "rawutil", c(364), "util")
  mydata <- adjust_other(mydata, "rawmedded", c(365), "med")
  mydata <- adjust_other(mydata, "rawdepded", c(323), "dep")
  mydata <- adjust_other(mydata, "rawcsded", c(366), "cs")

  valid_util <- mydata %>% group_by(state_name, year) %>% count(UTIL) %>%
    filter(n > 5) %>% select(state_name, year, UTIL)
  mydata <- mydata %>% rowwise() %>% mutate(
    rawutil = {
      if (!grepl("util", correctednotes)) rawutil
      else {
        valid <- valid_util$UTIL[valid_util$state_name == state_name & valid_util$year == year]
        if (correctednotes == "util_up") {
          valid <- valid[valid > UTIL]
          if (length(valid) == 0 || is.na(rawutil)) rawutil else valid[which.min(abs(valid - rawutil))]
        } else if (correctednotes == "util_down") {
          valid <- valid[valid < UTIL]
          if (length(valid) == 0 || is.na(rawutil)) 0 else valid[which.min(abs(valid - rawutil))]
        } else rawutil
      }
    }) %>% ungroup()
}

mydata <- calculate_raw_benefits(mydata)
ok <- abs(mydata$RAWBEN - mydata$rawben_recreated) <= 5
cat("national: rawben recreated within $5:", round(mean(ok, na.rm = TRUE) * 100, 2), "%\n")
err <- mydata$STATUS %in% c(2, 3)
cat("national error cases within $5:", round(mean(ok[err], na.rm = TRUE) * 100, 2), "%\n")

cols <- c("YRMONTH","HHLDNO","STATE","state_name","STATUS","AMTERR","RAWBEN","FSBEN","HWGT",
          "rawusize","rawearn","rawunearn","rawrent","rawutil","rawmedded","rawdepded","rawcsded",
          "rawstdded","rawhomeless_ded","rawbenmax","rawminimum_ben","rawernded","rawsltded",
          "rawnet_capped","rawben_recreated","at_max","over_threshold","correctednotes",
          "correctedamount","second_element_i","ded_fields_imputed","ELEMENT1","NATURE1","AGENCY1",
          "ELEMENT2","NATURE2","AGENCY2")
nat <- mydata[err, intersect(cols, names(mydata))]
write.csv(nat, paste0(out_dir, "fy2024_reconstruction_national.csv"), row.names = FALSE)
co <- nat[nat$STATE == 8, ]
write.csv(co, paste0(out_dir, "co_fy2024_reconstruction.csv"), row.names = FALSE)
cat("wrote", nrow(co), "CO error rows;", nrow(nat), "national error rows\n")
co_ok <- abs(co$RAWBEN - co$rawben_recreated) <= 5
cat("CO error cases within $5:", sum(co_ok, na.rm = TRUE), "of", nrow(co), "\n")
print(table(co$correctednotes))
