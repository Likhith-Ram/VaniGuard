# Smoke Test for Live Monitor UI

This test verifies the UI badge and rolling chart updates correctly across consecutive windows with different risk levels.
Streamlit apps are generally tested end-to-end (e.g. via Cypress, Playwright, or Streamlit's AppTest framework), but manual instructions are provided here as requested.

## Prerequisites
1. Start the Streamlit application: `streamlit run ui/app.py`
2. Open the app in your browser (usually http://localhost:8501)

## Setup Test File
To verify the Live Monitor, you'll need an audio file that will produce varying AI probabilities. 
You can run `python scratch/generate_test_audio.py` (assuming you write one) to produce a 10s audio file with alternating silence/noise that might produce different model outputs, or you can just rely on the fallback random predictions if the model is not loaded. If the model is not loaded, it will output random probabilities, which is perfect for testing the badge color changes across Green/Amber/Red!

## Test Steps
1. Navigate to the **" Live Monitor"** tab using the sidebar.
2. Ensure you see the upload widget, and upload any audio file (e.g. `wav` or `mp3` over 5 seconds long).
3. Click the **"Start Live Monitor"** button.

## Expected Behaviour
1. **Reset**: Upon clicking the start button, any previous badge or chart state should clear out, as `engine.reset()` is called.
2. **Streaming Updates**: The UI should update approximately every 0.5 seconds as audio chunks are processed.
3. **Badge Updates**: 
   - When the AI probability remains low, the badge should display **GREEN** using a green `st.success` box.
   - If the AI probability stays between 0.50 and 0.75 for 2 consecutive windows, the badge should change to **AMBER** using a yellow `st.warning` box.
   - If the AI probability exceeds 0.75 for 3 consecutive windows, the badge should change to **RED** using a red `st.error` box.
   *(Note: if testing without a model loaded, random values will eventually trigger these states).*
4. **Chart Updates**: 
   - A line chart should appear and grow with each processed window.
   - The chart should display exactly the last 5 windows at any given time (rolling window effect).

## Teardown
1. Wait for "Live monitor playback complete" to appear.
2. You may upload a different file and click Start again to verify that the state resets to 0 history.
