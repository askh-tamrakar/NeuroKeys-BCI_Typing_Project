import os
# MUST set backend before importing matplotlib.pyplot
os.environ.setdefault("MPLBACKEND", "Agg")

import asyncio
import time
import sys
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes
import numpy as np
import matplotlib.pyplot as plt


def prepare_board_for_reading_data(serial_port='COM7', board_id=38):
    params = BrainFlowInputParams()
    params.serial_port = serial_port

    try:
        board = BoardShim(board_id, params)
        board.prepare_session()
        print("Successfully Prepared Physical Board...")
    except Exception as error:
        print(f"\n❌ Error: {error}")
        print("Device could not be found or is being used somewhere else. Creating a Synthetic board Instead....\n")
        board_id = -1
        board = BoardShim(board_id, params)
        board.prepare_session()
        print("Successfully Prepared Synthetic Board...")

    return board


def eeg_data_isolation(board, board_id, data, out_path="eeg_plot.png"):
    # get_eeg_channels returns indices into rows of `data`
    eeg_channels = board.get_eeg_channels(board_id)
    if not eeg_channels:
        print("No EEG channels found for board_id:", board_id)
        return

    # data shape is (n_channels, n_samples)
    eeg_data = data[eeg_channels, :]
    n_ch, n_samples = eeg_data.shape
    print(f"EEG channels: {eeg_channels} -> shape: {eeg_data.shape}")

    # Plot each channel as a separate subplot to the same figure
    fig, axes = plt.subplots(n_ch, 1, figsize=(10, 2.5 * n_ch), squeeze=False)
    x = np.arange(n_samples)
    for i, ch_idx in enumerate(eeg_channels):
        ax = axes[i, 0]
        ax.plot(x, eeg_data[i, :])
        ax.set_ylabel(f"ch {ch_idx}")
        ax.set_xlim(0, n_samples - 1)
    axes[-1, 0].set_xlabel("Sample index")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved EEG plot to: {out_path}")

    eeg_data = data[eeg_channels[1]]
    graph = plt.plot(np.arange(eeg_data.shape[1]), eeg_data[0])


def main():
    print("\n\nStarting Stream...")
    board = prepare_board_for_reading_data()  # defaults: COM7 and board_id 38
    try:
        board.start_stream()
        time.sleep(5)  # collect some data
        data = board.get_board_data()  # returns ndarray (n_channels, n_samples)
    finally:
        print("Ending Stream!!!")
        try:
            board.stop_stream()
            board.release_session()
        except Exception:
            pass

    eeg_data_isolation(board, board.board_id, data)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
