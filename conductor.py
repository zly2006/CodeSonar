import random
import time

from scamp import Session, wait

from metronome import Metronome


class Conductor:

    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    SCALE = [0, 2, 4, 7, 9]  # Pentatonic Major

    # 王道进行 IV-V-iii-vi，相对于根音(C)的半音偏移 + 和弦类型
    # 和弦音程：大调=[0,7,16]（根/五/大十度），小调=[0,7,15]（根/五/小十度）
    PROGRESSION = [
        ("IV  F大", 5,  [0, 7, 16]),   # F major
        ("V   G大", 7,  [0, 7, 16]),   # G major
        ("iii E小", 4,  [0, 7, 15]),   # E minor
        ("vi  A小", 9,  [0, 7, 15]),   # A minor
    ]

    def __init__(self, sensor):
        self.sensor = sensor
        self.metro = Metronome()
        self.session = Session(tempo=self.metro.bpm)

        try:
            self.pad      = self.session.new_part("Electric Piano 1")
            self.droplets = self.session.new_part("Vibraphone")
            self.bass     = self.session.new_part("Fretless Bass")
        except Exception:
            self.pad      = self.session.new_part("Piano")
            self.droplets = self.session.new_part("Piano")
            self.bass     = self.session.new_part("Piano")

        self.root    = 60   # Middle C
        self.running = True

        # Smoothed sensor values (written by loop_sensor_update, read everywhere)
        self.cpu = 0.0
        self.ram = 0.0
        self.net = 0.0

    # ------------------------------------------------------------------ helpers

    def _name(self, midi: int) -> str:
        return f"{self.NOTE_NAMES[midi % 12]}{midi // 12 - 1}"

    def _scale_pitch(self, base: int, octave_offset: int = 0) -> int:
        return base + random.choice(self.SCALE) + octave_offset * 12

    def _log(self, tag: str, instrument: str, pitch_or_notes, vol: float,
             beats: float, reason: str):
        ts = time.strftime("%H:%M:%S")
        bar  = self.metro.bar_count
        beat = self.metro.beat_in_bar
        sig  = self.metro.sig_label()
        bpm  = self.metro.bpm

        if isinstance(pitch_or_notes, list):
            pitch_str = str([self._name(n) for n in pitch_or_notes])
        else:
            pitch_str = f"{self._name(pitch_or_notes)} (MIDI {pitch_or_notes})"

        print(
            f"[{tag:<5}] {ts} | Bar {bar:>3} Beat {beat} {sig} BPM={bpm:>4.0f} | "
            f"音色:{instrument:<14} 音高:{pitch_str:<22} 力度:{vol:.2f} 时值:{beats:.1f}拍 | "
            f"{reason} | CPU={self.cpu:.0%} RAM={self.ram:.0%} NET={self.net:.0%}"
        )

    # ------------------------------------------------------------------ loops

    def loop_sensor_update(self):
        """Reads sensors every beat and pushes targets to metronome."""
        while self.running:
            self.sensor.update()
            self.cpu, self.ram, self.net = self.sensor.get_smoothed_metrics()
            self.metro.update_targets(self.cpu, self.ram, self.net)
            wait(1.0)

    def loop_clock(self):
        """
        Master beat clock. Fires every 1 beat.
        Updates session tempo and drives the Metronome state machine.
        This is the only place that calls metro.tick().
        """
        while self.running:
            beat, is_downbeat = self.metro.tick()
            # Apply BPM to SCAMP session (affects real-world speed of wait())
            self.session.tempo = self.metro.bpm

            if is_downbeat:
                print(
                    f"\n{'─'*20} Bar {self.metro.bar_count} | "
                    f"{self.metro.sig_label()} | BPM={self.metro.bpm:.0f} "
                    f"{'─'*20}"
                )

            wait(1.0)

    def loop_pad(self):
        """
        Pad: plays one chord per bar, cycling through IV-V-iii-vi progression.
        Chord changes only on the downbeat (beat 0), never mid-bar.
        """
        while self.running:
            ts = self.metro.time_sig
            base = self.root - 12  # C3

            # Pick chord from progression based on bar index (cycles every 4 bars)
            prog_idx = (self.metro.bar_count - 1) % len(self.PROGRESSION)
            chord_name, root_offset, intervals = self.PROGRESSION[prog_idx]
            chord_root = base + root_offset
            notes = [chord_root + i for i in intervals]

            vol = 0.28 + self.cpu * 0.18
            sustain = ts * 0.92
            gap     = ts - sustain

            reason = (
                f"{chord_name} (Bar {self.metro.bar_count}，共{ts}拍)"
            )
            self._log("PAD", "ElecPiano", notes, vol, ts, reason)
            self.pad.play_chord(notes, vol, sustain, blocking=True)
            wait(gap)

    def loop_droplets(self):
        """
        Droplets: fires probabilistically on EACH beat (excluding the downbeat).
        This ensures droplets ornament within the bar, never clash with chord changes.

        Beat 0 (downbeat): skip — pad owns it.
        Beat 1..time_sig-1: probabilistic, weighted by CPU.
        Network activity triggers high-octave sparkle notes.
        """
        while self.running:
            beat = self.metro.beat_in_bar

            if beat == 0:
                # Downbeat: silence (pad is attacking its chord here)
                wait(1.0)
                continue

            prob = 0.20 + self.cpu * 0.80
            if random.random() >= prob:
                wait(1.0)
                continue

            # Decide octave: net activity sparks high notes
            net_sparkle = self.net > 0.20 and random.random() < self.net
            octave = 2 if net_sparkle else 1  # root+12 or root+24 above middle C
            pitch = self._scale_pitch(self.root, octave)
            vol = 0.18 + self.cpu * 0.35 + (self.net * 0.12 if net_sparkle else 0)
            # Duration: 70% of one beat (short, crisp)
            sustain = 0.70

            if net_sparkle:
                reason = (
                    f"网络流量高({self.net:.0%})→高八度闪光音 "
                    f"(Beat {beat}/{self.metro.time_sig-1})"
                )
            else:
                reason = (
                    f"CPU活跃({self.cpu:.0%})→脉冲点缀 "
                    f"(Beat {beat}/{self.metro.time_sig-1}, prob={prob:.0%})"
                )

            self._log("DROP", "Vibraphone", pitch, vol, sustain, reason)
            self.droplets.play_note(pitch, vol, sustain)
            wait(1.0 - sustain)  # fill rest of beat

    def loop_bass(self):
        """
        Bass: holds one note for 2 full bars, then changes.
        Duration = time_sig × 2 beats — always an exact multiple of the bar.
        RAM drives pitch: high RAM sinks the bass a fourth deeper.
        """
        while self.running:
            ts    = self.metro.time_sig
            bars  = 2
            total = ts * bars  # e.g. 8 beats in 4/4, 6 in 3/4

            pitch = self.root - 24  # two octaves below middle C
            if self.ram > 0.80:
                pitch -= 5  # drop a fourth (5 semitones)
                reason = f"RAM过高({self.ram:.0%})→低音下沉四度，两小节({total}拍)持续"
            else:
                reason = f"根音持续，RAM={self.ram:.0%}，横跨{bars}小节({total}拍)"

            self._log("BASS", "FretlessBass", pitch, 0.38, total, reason)
            self.bass.play_note(pitch, 0.38, total * 0.92)
            wait(total * 0.08)  # brief gap before next bass note

    # ------------------------------------------------------------------

    def start(self):
        # Fork order matters: sensor_update and clock go first
        self.session.fork(self.loop_sensor_update)
        self.session.fork(self.loop_clock)
        self.session.fork(self.loop_pad)
        self.session.fork(self.loop_bass)
        self.session.fork(self.loop_droplets)
        self.session.wait_forever()
