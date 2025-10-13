from chromatography_process import ChromatographyProcess, ChromatographyStepLibrary, ChromatographyStep

# Create process and add steps
process = ChromatographyProcess()
process.create_standard_purification_process()  # Adds 5

# Run the complete process
process.run_process()
