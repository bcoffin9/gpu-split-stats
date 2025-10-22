import os
from bisect import bisect_left
import pandas as pd
import gpxpy
from datetime import timedelta
from geopy.distance import geodesic

ALLOWED_STEPS = {
    'meters': [100, 200, 400, 600, 800, 1000, 1200, 1600, 2000, 3200, 5000, 10000],
    'km': [1, 2, 5, 10, 20],
    'mi': [0.25, 0.5, 1, 2, 3, 4, 5, 10, 13.1]
}

UNIT_CONVERSIONS = {
    'meters': 1,
    'km': 1000,
    'mi': 1609.34
}


def prepare_gpx_dataframe(gpx_file_path):
    """
    Parse a GPX file and prepare a DataFrame with time, coordinates, elevation,
    segment distance, cumulative distance, and elapsed time.

    Parameters:
    -----------
    gpx_file_path : str
        Path to the .gpx file

    Returns:
    --------
    pandas.DataFrame
        DataFrame containing GPS point data and computed metrics
    string
        A string containing the title of the event as recorded, "" if not found
    """
    if isinstance(gpx_file_path, (str, bytes, os.PathLike)):
        with open(gpx_file_path, 'r') as f:
            gpx = gpxpy.parse(f)
    else:
        gpx = gpxpy.parse(gpx_file_path)

    title = ""

    points = []
    for track in gpx.tracks:
        title = track.name
        for segment in track.segments:
            for point in segment.points:
                points.append({
                    'time': point.time,
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'elevation': point.elevation
                })

    df = pd.DataFrame(points)
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values(by='time').reset_index(drop=True)

    # Calculate distances
    distances = [0]
    for i in range(1, len(df)):
        prev = (df.loc[i-1, 'latitude'], df.loc[i-1, 'longitude'])
        curr = (df.loc[i, 'latitude'], df.loc[i, 'longitude'])
        distances.append(geodesic(prev, curr).meters)

    df['segment_meters'] = distances
    df['cumulative_meters'] = df['segment_meters'].cumsum()
    df['elapsed_time'] = (df['time'] - df['time'].iloc[0]).dt.total_seconds()

    return df, title


def compute_splits(df, unit='meters', step=1000):
    """
    Calculate estimated split times and paces based on a GPS activity DataFrame.

    Parameters:
    -----------
    df : pandas.DataFrame
        A DataFrame with the following required columns:
        - 'time': Timestamps of each GPS point (datetime)
        - 'cumulative_meters': Cumulative distance in meters
        - 'elapsed_time': Elapsed time in seconds since the start

    unit : str
        The unit to calculate splits in. One of: 'meters', 'km', or 'mi'.

    step : float
        The split interval to use, which must be from the allowed set for the chosen unit:
        - 'meters': [100, 200, 400, 600, 800, 1000, 1200, 1600, 2000, 3200, 5000, 10000]
        - 'km': [1, 2, 5, 10, 20]
        - 'mi': [0.25, 0.5, ..., 13.1]  (increments of 0.25)

    Returns:
    --------
    pandas.DataFrame
        A DataFrame with the following columns:
        - <unit>_split: Distance marker at each split
        - elapsed_time_sec: Total elapsed time at that marker
        - split_time_sec: Time to complete that split
        - pace: Pace for the split, formatted as MM:SS

    Raises:
    -------
    ValueError
        If an unsupported unit or step size is provided.
    """
    if unit not in ALLOWED_STEPS:
        raise ValueError(
            f"Invalid unit '{unit}'. Must be one of {list(ALLOWED_STEPS.keys())}.")

    if step not in ALLOWED_STEPS[unit]:
        raise ValueError(
            f"Step value '{step}' not allowed for unit '{unit}'. Allowed: {ALLOWED_STEPS[unit]}")

    df['distance_unit'] = df['cumulative_meters'] / UNIT_CONVERSIONS[unit]
    max_unit_distance = df['distance_unit'].iloc[-1]

    # Create split markers
    split_markers = []
    current = step
    while current < max_unit_distance:
        split_markers.append(round(current, 2))
        current += step

    split_data = []

    for marker in split_markers:
        idx = bisect_left(df['distance_unit'].values, marker)
        if idx == 0 or idx >= len(df):
            continue

        split_data.append({
            f'{unit}_split': marker,
            'elapsed_time_sec': df.loc[idx, 'elapsed_time']
        })

    # Add final partial split if needed
    final_distance = round(df['distance_unit'].iloc[-1], 2)
    final_time = df['elapsed_time'].iloc[-1]

    if not split_markers or final_distance > split_markers[-1]:
        split_data.append({
            f'{unit}_split': final_distance,
            'elapsed_time_sec': final_time
        })

    split_df = pd.DataFrame(split_data)

    split_df['split_time_sec'] = split_df['elapsed_time_sec'].diff().fillna(
        split_df['elapsed_time_sec'])

    # Split Time formats
    split_df['split_pace_mmss'] = split_df['split_time_sec'].apply(
        lambda x: str(timedelta(seconds=int(x)))[
            2:] if x < 3600 else str(timedelta(seconds=int(x)))
    )
    split_df['split_pace_hhmmss'] = split_df['split_time_sec'].apply(
        lambda x: str(timedelta(seconds=int(x))).rjust(8, "0")
    )

    # Compute distances between splits
    # First distance is from 0
    split_distances = [split_df[f'{unit}_split'].iloc[0]]
    # Remainder diffs
    split_distances += list(split_df[f'{unit}_split'].diff().iloc[1:])
    split_df['split_distance'] = split_distances

    # Adjusted pace: normalized to input step size
    split_df['pace_seconds'] = split_df['split_time_sec'] / \
        split_df['split_distance']
    split_df['pace_seconds'] = split_df['pace_seconds'].round(2)

    # Unit Pace Time formats
    split_df['pace_mmss'] = split_df['pace_seconds'].apply(
        lambda x: str(timedelta(seconds=int(x)))[
            2:] if x < 3600 else str(timedelta(seconds=int(x)))
    )
    split_df['pace_hhmmss'] = split_df['pace_seconds'].apply(
        lambda x: str(timedelta(seconds=int(x))).rjust(8, "0")
    )

    split_df['pace'] = split_df['pace_mmss']

    return split_df


if __name__ == "__main__":
    df = prepare_gpx_dataframe("input/activity_18818451412.gpx")
    splits = compute_splits(df, unit="mi", step=1.0)
    print(splits.head())

    splits = compute_splits(df, unit="meters", step=400)
    print(splits.head())

    splits = compute_splits(df, unit="km", step=5)
    print(splits)

    splits = compute_splits(df, unit="mi", step=13.1)
    print(splits)
