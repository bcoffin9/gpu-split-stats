import streamlit as st
import altair as alt
from split_calculator import prepare_gpx_dataframe, compute_splits, ALLOWED_STEPS
import io

# -----------------------------
# Streamlit App Configuration
# -----------------------------
st.set_page_config(page_title="Marathon GPX Split Viewer", layout="wide")
st.title("🏃‍♂️ Marathon Split Visualizer")

# -----------------------------
# File Upload
# -----------------------------
st.sidebar.header("Upload GPX File")
uploaded_file = st.sidebar.file_uploader("Choose a .gpx file", type="gpx")

if uploaded_file:
    gpx_bytes = uploaded_file.read()
    gpx_stream = io.StringIO(gpx_bytes.decode("utf-8"))
    df, title = prepare_gpx_dataframe(gpx_stream)

    # -----------------------------
    # Unit and Split Controls
    # -----------------------------
    st.sidebar.header("Split Settings")
    unit = st.sidebar.selectbox(
        "Unit", options=["meters", "km", "mi"], index=1)
    step = st.sidebar.selectbox("Split Interval", options=ALLOWED_STEPS[unit])
    time_format = st.sidebar.selectbox(
        "Time Format", options=["pace_mmss", "pace_hhmmss", "pace_seconds"], index=0)

    # -----------------------------
    # Display Basic Info
    # -----------------------------
    total_distance_km = df["cumulative_meters"].iloc[-1] / 1000
    total_distance_mi = df["cumulative_meters"].iloc[-1] / 1609.34

    col1, col2 = st.columns(2)
    col1.metric("Total Distance (km)", f"{total_distance_km:.2f} km")
    col2.metric("Total Distance (mi)", f"{total_distance_mi:.2f} mi")

    # -----------------------------
    # Compute and Display Splits
    # -----------------------------
    splits = compute_splits(df, unit=unit, step=step)

    chart = alt.Chart(splits).mark_line(point=True).encode(
        x=alt.X(f"{unit}_split:Q", title=f"Distance ({unit})"),
        y=alt.Y("pace_seconds:Q",
                title=f"{unit} Pace (s)"),
        tooltip=[
            f"{unit}_split", "split_time_sec", "pace_mmss", "pace_hhmmss", "pace_seconds"
        ]
    ).properties(height=400)

    st.subheader(f"{title}")
    st.subheader(f"{unit} Pace per {step} {unit}")

    st.altair_chart(chart, use_container_width=True)

    # -----------------------------
    # Table View
    # -----------------------------
    st.subheader("Split Table")
    pace_display = splits[[f"{unit}_split", "split_time_sec", "split_pace_mmss", "split_pace_hhmmss",
                           "pace_seconds", "pace_mmss", "pace_hhmmss"]].copy()
    pace_display.columns = [f"{unit.title()} Split", "Split Duration (s)", "Split Pace (MM:SS)", "Split Pace (HH:MM:SS)",
                            f"{unit.title()} Pace (sec)", f"{unit.title()} Pace (MM:SS)", f"{unit.title()} Pace (HH:MM:SS)"]
    st.dataframe(pace_display, use_container_width=True)

else:
    st.info("📂 Upload a GPX file from your marathon to get started!")
