import multiprocessing
import sys


def cpu_stress():
    """
    一个无意义的死循环死计算，用于榨干单个 CPU 核心的性能。
    """
    while True:
        pass


if __name__ == '__main__':
    # 获取当前机器的逻辑 CPU 核心数
    core_count = multiprocessing.cpu_count()
    print(f"检测到 {core_count} 个 CPU 核心。")
    print("正在启动满载压力测试... (按 Ctrl+C 停止)")

    processes = []

    try:
        # 为每个核心启动一个进程
        for i in range(core_count):
            p = multiprocessing.Process(target=cpu_stress)
            p.start()
            processes.append(p)

        # 保持主进程运行
        for p in processes:
            p.join()

    except KeyboardInterrupt:
        # 捕获 Ctrl+C 终止信号，安全退出
        print("\n正在停止压力测试，清理进程中...")
        for p in processes:
            p.terminate()
            p.join()
        print("所有进程已终止。")
        sys.exit(0)