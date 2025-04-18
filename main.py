import argparse
import logging
import multiprocessing as mp
import queue
import threading
from math import ceil

import jack
import numpy as np
import rich
from PIL import Image


def xrun(delay):
    print("Got an xrun :(", delay)


def createJackClient(
    name: str,
    channel_num: int,
    ievent: threading.Event,
    isevent: threading.Event,
    oevent: threading.Event,
    iq: queue.Queue,
    oq: queue.Queue,
) -> jack.Client:
    client = jack.Client(name)
    blocksize = client.blocksize
    for n in range(channel_num):
        client.outports.register(f"output_{n + 1}")
        client.inports.register(f"input_{n + 1}")

    def shutdown(status, reason):
        print("Jack Shutdown!")
        print(f"\tstatus: {status}")
        print(f"\treason: {reason}")
        oevent.set()
        ievent.set()

    def stop_callback(msg="", evnt=oevent):
        if msg:
            print(msg)
        for port in client.inports:
            port.get_array().fill(-3)
        oevent.set()
        ievent.set()
        isevent.clear()
        raise jack.CallbackExit

    def process(frames):
        if frames != blocksize:
            stop_callback("blocksize changed, stopping!")
        try:
            odata = oq.get_nowait()
            if odata is not None:
                for channel, port in zip(odata.T, client.outports):
                    port.get_array()[:] = channel
        except queue.Empty:
            pass
            # stop_callback("Buffer empty, stopping!")
        data = []
        for port in client.inports:
            rec = port.get_array()
            data.append(rec)
        # print([(x == -1).any() or (x == -2).any() for x in data])
        data = np.stack(data, -1)
        if isevent.is_set():
            iq.put_nowait(np.where(data < 0, 0, data))
        if (data == -1).any():
            iq.shutdown()
            stop_callback()
        elif (data == -2).any():
            isevent.set()

    client.set_xrun_callback(xrun)
    client.set_shutdown_callback(shutdown)
    client.set_process_callback(process)

    client.activate()
    return client


def closest_multiple(x, mul):
    rem = x % mul
    return x - rem if rem < (mul / 2) else x + (mul - rem)


def playImage(
    blocksize: int,
    img: Image.Image,
    event: threading.Event,
    q: queue.Queue,
    single_channel: bool = False,
):
    data = (
        np.array(img)
        .reshape((-1, 1, 1 if single_channel else len(img.getbands())))
        .squeeze()
    )
    num_blocks = ceil(data.shape[0] / blocksize)
    closest = closest_multiple(data.shape[0], blocksize)
    rem = (
        closest - data.shape[0]
        if closest >= data.shape[0]
        else (closest + blocksize) - data.shape[0]
    )
    padding_amnt = ((0, rem), (0, 0)) if not single_channel else ((0, rem))
    data = np.pad(data, pad_width=padding_amnt, mode="constant", constant_values=0)
    chunks = np.split(data, num_blocks)
    q.put(np.full_like(chunks[0], -2, dtype=np.float32))
    print("sent start signal")
    for b in chunks:
        q.put(b / 256)
    q.put(np.full_like(chunks[0], -1, dtype=np.float32))
    print("sent end signal")
    q.put(None)
    event.wait()


def listenImage(
    blocksize: int,
    img: Image.Image,
    event: threading.Event,
    q: queue.Queue,
    single_channel: bool = False,
):
    recv_data = []
    print("listening to data")
    while True:
        try:
            qdat = q.get()
            # if single_channel:
            #     for c in range(len(img.getbands()) - 1):
            #         qdat = np.hstack([qdat, q.get()])
            recv_data.append(qdat * 256)
        except queue.ShutDown:
            print("stopped listening")
            break
    # print(len(recv_data), recv_data[0].shape)
    recv_data = np.concat(recv_data, 0)
    # if single_channel:
    #     recv_data = np.stack(np.split(recv_data.squeeze(), len(img.getbands())), -1)
    print(recv_data.shape)
    data = (
        np.array(img)
        .reshape((-1, 1, 1 if single_channel else len(img.getbands())))
        .squeeze()
    )
    pal = img.palette
    print(np.stack(np.split(recv_data[: data.shape[0]], img.size[1])).shape)
    img = Image.fromarray(
        np.stack(np.split(recv_data[: data.shape[0]], img.size[1]))
        .squeeze()
        .astype(np.uint8),
        mode="".join(list(img.getbands())),
    )
    if pal:
        img.putpalette(pal)
    print(np.array(img).shape)
    img.show()


def main():
    parser = argparse.ArgumentParser(
        prog="Image2Jackaudio",
        description="Turns images into Audiostreams and back for databending",
    )
    parser.add_argument("inputimage")
    parser.add_argument("outputimage")
    parser.add_argument(
        "-s",
        "--split",
        action="store_true",
        help="create one audiostream per image channel",
    )
    parser.add_argument("-n", "--name", default="Img2Jack", help="the Jack Client name")
    parser.add_argument(
        "-a",
        "--autoconnect",
        action="store_true",
        help="try to connect to output automatically",
    )
    parser.add_argument(
        "--cinpat",
        default="cv_in_*",
        help="regex pattern of the input connections to autoconnect to",
    )
    parser.add_argument(
        "--coutpat",
        default="cv_out_*",
        help="regex pattern of the output connections to autoconnect to",
    )
    args = parser.parse_args()
    with mp.Manager() as manager:
        iq = manager.Queue()
        oq = manager.Queue()
        ievent = manager.Event()
        isevent = manager.Event()
        oevent = manager.Event()

        in_image = Image.open(args.inputimage)
        if in_image.getbands()[0] == "P":
            in_image = in_image.convert(
                "RGBA",
                palette=Image.Palette.ADAPTIVE,
            )
        out_image = in_image.copy()

        with createJackClient(
            args.name,
            len(in_image.getbands()) if args.split else 1,
            ievent,
            isevent,
            oevent,
            iq,
            oq,
        ) as client:
            if args.autoconnect:
                available_in_ports = client.get_ports(
                    args.cinpat, is_audio=True, is_input=True
                )
                available_out_ports = client.get_ports(
                    args.coutpat, is_audio=True, is_output=True
                )
                for c in range(len(in_image.getbands()) if args.split else 1):
                    client.outports[c].connect(available_in_ports[c])
                for c in range(len(in_image.getbands()) if args.split else 1):
                    client.inports[c].connect(available_out_ports[c])
            blocksize = client.blocksize
            print(blocksize)
            # listenImage(blocksize, args.outputimage, ievent, iq, not args.split)
            pp = mp.Process(
                target=playImage,
                args=[blocksize, in_image, oevent, oq, not args.split],
            )
            lp = mp.Process(
                target=listenImage,
                args=[blocksize, out_image, ievent, iq, not args.split],
            )
            # try:
            #     while True:
            #         pass
            # except KeyboardInterrupt:
            # print()
            pp.start()
            lp.start()
            pp.join()
            lp.join()


if __name__ == "__main__":
    main()
