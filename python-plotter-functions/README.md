# Correlation heatmap

Use this plot to compare selected signals by their Pearson cross-correlation coefficients and the time shifts that produce the strongest correlations.

## Use

1. Add between 2 and 30 numeric signals to the Details Pane.
2. Set the Display Pane range to the period you want to analyze.
3. Select **Correlation Heatmap** in Python Plotter.
4. Open the plot options to choose the output, filters, and allowed shift.

The rows identify the original signal. The columns identify the signal shifted in time. Hover over a cell to see both the coefficient and the maximizing time shift.

## Options

- **Maximum time shift** controls how far signals may move while searching for the strongest absolute correlation. Choose **No time shift** for ordinary Pearson correlations.
- **Display** switches the output values between coefficients and time shifts.
- **Output type** switches between a heatmap and a table.
- **Time-shift units** controls the units shown in the heatmap, table, and tooltip.
- **Show values in cells** adds numeric labels to the heatmap.
- **Maximum label characters** shortens long signal names while keeping both ends recognizable.
- **Coefficient lower bound** and **Coefficient upper bound** keep coefficients inside the selected range. Enable **Use outer coefficient range** to keep values outside it instead.
- Enable **Filter time shifts** to apply the time-shift bounds. These bounds use the selected time-shift units. **Use outer time-shift range** keeps values outside those bounds.

## Data handling

The plot uses the selected Display Pane range. The existing Correlation preprocessing removes nonnumeric and flat signals, fills short gaps, rejects signals with remaining missing data, and standardizes values before calculating correlations.
