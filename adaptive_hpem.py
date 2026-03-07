import numpy as np
import random
import math
import matplotlib.pyplot as plt
import heapq
import struct
import time
import psutil
# 假设这些是你本地的辅助函数库
from OLH import OLH, OLH_file
from OLH_nt import OLH_nt
from set_wheel import set_wheel, set_wheel_file
from set_wheel_nt import set_wheel_nt
from read_data_dist import read_data


# ===================== 原方案核心逻辑 (已移除adaptive剪枝) =====================
def data_to_prefix(X, N, g, c, m, k):
    """生成前缀数据，存储为二维列表"""
    si = [0] * (g + 1)
    prefix_X = [[0 for _ in range(c)] for _ in range(N)]
    r_N = math.ceil(N / g)

    # 计算每个阶段的前缀长度
    for i in range(1, g + 1):
        si[i] = math.ceil(math.log2(k)) + math.ceil(i * (m - math.ceil(math.log2(k))) / g)

    # 生成前缀
    for i in range(1, g + 1):
        r_start = (i - 1) * r_N
        r_stop = N if i == g else i * r_N

        for j in range(r_start, r_stop):
            for t_j in range(c):
                x = X[j][t_j]
                s = si[i]
                # 整数转二进制并截取前缀
                prefix = int('{:064b}'.format(int(x))[0:s], 2) if s > 0 else 0
                prefix_X[j][t_j] = prefix

    return prefix_X, si


def split_prefix_X_nt(prefix_X, r, g, N):
    """分割出指定阶段的数据"""
    r_N = math.ceil(N / g)
    r_start = (r - 1) * r_N
    r_stop = N if r == g else r * r_N
    t_X = prefix_X[r_start:r_stop]
    return t_X, r_stop - r_start


def PEM_OLH_nt(prefix_X, k, m, g, c, epsilon, N, si):
    """原方案OLH算法（不支持自适应剪枝）"""
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))

    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X_nt(prefix_X, i, g, N)

        # 始终使用完整的候选集D
        D = construct_D(Ct, k, m, i, g)

        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        if use_file:
            construct_D_file(Ct, k, m, i, g)
            OLH_file(t_X, Ni, c, epsilon, i)
            Ct, OLH_dist = construct_C_file(k, i)
        else:
            EstimateDist_OlH = OLH_nt(t_X, Ni, c, epsilon, D)
            Ct, OLH_dist = construct_C(EstimateDist_OlH, k, D)

    return Ct, OLH_dist


def PEM_wheel_nt(prefix_X, k, m, g, c, epsilon, N, si):
    """原方案Wheel算法（不支持自适应剪枝）"""
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))

    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X_nt(prefix_X, i, g, N)

        # 始终使用完整的候选集D
        D = construct_D(Ct, k, m, i, g)

        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        if use_file:
            construct_D_file(Ct, k, m, i, g)
            set_wheel_file(t_X, Ni, c, epsilon, i)
            Ct, wheel_dist = construct_C_file(k, i)
        else:
            EstimateDist_wheel = set_wheel_nt(t_X, Ni, c, epsilon, D)
            Ct, wheel_dist = construct_C(EstimateDist_wheel, k, D)

    return Ct, wheel_dist


# ===================== 二进制Trie树结构 (保留，因为PEM_OLH/Wheel仍在使用) =====================
class BinaryTrieNode:
    def __init__(self):
        self.children = [None, None]
        self.count = 0
        self.is_leaf = False


class BinaryTrie:
    def __init__(self, prefix_length):
        self.root = BinaryTrieNode()
        self.prefix_length = prefix_length

    def insert(self, binary_value):
        binary_str = bin(binary_value)[2:].zfill(self.prefix_length)
        if len(binary_str) > self.prefix_length:
            binary_str = binary_str[-self.prefix_length:]

        node = self.root
        for bit in binary_str:
            bit_idx = int(bit)
            if not node.children[bit_idx]:
                node.children[bit_idx] = BinaryTrieNode()
            node = node.children[bit_idx]
            node.count += 1

        node.is_leaf = True

    def get_count(self, binary_value):
        binary_str = bin(binary_value)[2:].zfill(self.prefix_length)
        if len(binary_str) > self.prefix_length:
            binary_str = binary_str[-self.prefix_length:]

        node = self.root
        for bit in binary_str:
            bit_idx = int(bit)
            if not node.children[bit_idx]:
                return 0
            node = node.children[bit_idx]
        return node.count if node.is_leaf else 0

    def get_prefix_count(self, prefix_value, prefix_length):
        binary_str = bin(prefix_value)[2:].zfill(prefix_length)
        if len(binary_str) > prefix_length:
            binary_str = binary_str[-prefix_length:]

        node = self.root
        for bit in binary_str:
            bit_idx = int(bit)
            if not node.children[bit_idx]:
                return 0
            node = node.children[bit_idx]
        return node.count

    def get_top_k(self, k):
        top_k = []

        def dfs(node, current_path):
            if node.is_leaf:
                value = int(''.join(current_path), 2)
                heapq.heappush(top_k, (-node.count, value))
                if len(top_k) > k:
                    heapq.heappop(top_k)
                return

            children = []
            for bit in [0, 1]:
                if node.children[bit]:
                    children.append((-node.children[bit].count, bit))

            for _, bit in sorted(children):
                current_path.append(str(bit))
                dfs(node.children[bit], current_path)
                current_path.pop()

        dfs(self.root, [])

        result = []
        while top_k:
            count, value = heapq.heappop(top_k)
            result.append((value, -count))
        return result[::-1]

    def get_all_elements(self):
        elements = {}

        def dfs(node, current_path):
            if node.is_leaf:
                value = int(''.join(current_path), 2)
                elements[value] = node.count
                return

            for bit in [0, 1]:
                if node.children[bit]:
                    current_path.append(str(bit))
                    dfs(node.children[bit], current_path)
                    current_path.pop()

        dfs(self.root, [])
        return elements


# ===================== 工具函数 =====================
def get_available_memory():
    """获取可用内存（MB）"""
    return psutil.virtual_memory().available / (1024 ** 2)


def data_to_prefix_t(X, N, g, c, m, k):
    """生成前缀并存储到Trie字典中，每个阶段一个Trie"""
    si_trie = [0] * (g + 1)
    r_N = math.ceil(N / g)

    for i in range(1, g + 1):
        si_trie[i] = math.ceil(math.log2(k)) + math.ceil(i * (m - math.ceil(math.log2(k))) / g)

    stage_tries = {}
    for i in range(1, g + 1):
        r_start = (i - 1) * r_N
        r_stop = N if i == g else i * r_N
        s = si_trie[i]

        trie = BinaryTrie(prefix_length=s)
        for j in range(r_start, r_stop):
            for t_j in range(c):
                x = X[j][t_j]
                prefix = (x >> (64 - s)) if s != 0 else 0
                trie.insert(prefix)

        stage_tries[i] = trie

    return stage_tries, si_trie


def split_prefix_X(stage_tries, r):
    """从Trie中获取指定阶段的数据和数量"""
    trie = stage_tries[r]
    elements = trie.get_all_elements()
    t_X = [[val] for val in elements.keys() for _ in range(elements[val])]
    return t_X, sum(elements.values())


# ===================== 候选集构建 (已移除construct_D_adaptive) =====================
def construct_D(Ct, k, m, r, g):
    """基础候选集D构建（无剪枝）"""
    sr = math.ceil(math.log2(k)) + math.ceil(r * (m - math.ceil(math.log2(k))) / g)
    sr1 = math.ceil(math.log2(k)) if r == 1 else \
        math.ceil(math.log2(k)) + math.ceil((r - 1) * (m - math.ceil(math.log2(k))) / g)

    s_len = sr - sr1
    sl = 1 << s_len  # 2^s_len

    D = []
    for ct_val in Ct:
        prefix = ct_val << s_len
        for suffix in range(sl):
            D.append(prefix | suffix)
    return D


def construct_D_file(Ct, k, m, r, g):
    """二进制文件存储候选集D"""
    sr = math.ceil(math.log2(k)) + math.ceil(r * (m - math.ceil(math.log2(k))) / g)
    sr1 = math.ceil(math.log2(k)) if r == 1 else \
        math.ceil(math.log2(k)) + math.ceil((r - 1) * (m - math.ceil(math.log2(k))) / g)

    s_len = sr - sr1
    sl = 1 << s_len
    filename = f'../../temp/olh/D{r}.bin'

    estimated_size = k * sl * 8
    if estimated_size > get_available_memory() * 1024 * 1024 * 0.5:
        with open(filename, 'wb') as f:
            for ct_val in Ct:
                prefix = ct_val << s_len
                for chunk in range(0, sl, 10000):
                    end = min(chunk + 10000, sl)
                    data = b''.join([struct.pack('Q', prefix | suffix) for suffix in range(chunk, end)])
                    f.write(data)
    else:
        with open(filename, 'wb') as f:
            for ct_val in Ct:
                prefix = ct_val << s_len
                data = b''.join([struct.pack('Q', prefix | suffix) for suffix in range(sl)])
                f.write(data)

    return 0


def read_D_file(r):
    """从二进制文件读取候选集D"""
    filename = f'../../temp/olh/D{r}.bin'
    D = []
    with open(filename, 'rb') as f:
        while True:
            data = f.read(8)
            if not data:
                break
            D.append(struct.unpack('Q', data)[0])
    return D


# ===================== Top-k构建与评估 =====================
def construct_C(C1, k, D):
    """从估计分布中构建Top-k候选集"""
    heap = []
    for i, count in enumerate(C1):
        if len(heap) < k:
            heapq.heappush(heap, (count, i))
        else:
            if count > heap[0][0]:
                heapq.heappop(heap)
                heapq.heappush(heap, (count, i))

    top_k = sorted(heap, key=lambda x: -x[0])
    top_k_data = [D[idx] for (count, idx) in top_k]
    top_k_dist = [count for (count, idx) in top_k]
    return top_k_data, top_k_dist


def construct_C_file(k, r):
    """从文件中构建Top-k候选集"""
    top_k_data = []
    top_k_dist = []
    heap = []

    file_d_name = f'../../temp/olh/D{r}.bin'
    file_dist_name = f'../../temp/olh/dist{r}.txt'

    with open(file_dist_name, 'r') as dist_file, open(file_d_name, 'rb') as d_file:
        dist_line = dist_file.readline()
        while dist_line:
            dist = float(dist_line.strip())
            data_bytes = d_file.read(8)
            if not data_bytes:
                break

            data = struct.unpack('Q', data_bytes)[0]

            if len(heap) < k:
                heapq.heappush(heap, (dist, data))
            else:
                if dist > heap[0][0]:
                    heapq.heappop(heap)
                    heapq.heappush(heap, (dist, data))

            dist_line = dist_file.readline()

    top_k = sorted(heap, key=lambda x: -x[0])
    top_k_data = [data for (dist, data) in top_k]
    top_k_dist = [dist for (dist, data) in top_k]
    return top_k_data, top_k_dist


def cal_f1(ct, cg):
    """计算F1分数"""
    common = set(ct) & set(cg)
    lc = len(common)
    if lc == 0:
        return 0.0

    p = lc / len(ct)
    r = lc / len(cg)
    return 2 * p * r / (p + r)


def cal_ncr(ct, cg, dist_ct, dist_cg, k):
    """计算NCR分数"""
    dist_t1 = dist_ct.copy()
    dist_t2 = dist_cg.copy()

    order_ct = []
    order_cg = []

    for _ in range(k):
        t_index1 = dist_t1.index(max(dist_t1))
        order_ct.append(ct[t_index1])
        dist_t1[t_index1] = -1

        t_index2 = dist_t2.index(max(dist_t2))
        order_cg.append(cg[t_index2])
        dist_t2[t_index2] = -1

    ncr = 0
    for i, t in enumerate(order_ct):
        if t in order_cg:
            ncr += (k - order_cg.index(t))

    denominator = k * (k + 1) / 2
    return ncr / denominator if denominator != 0 else 0.0


def cal_mse(pred_dist, real_dist):
    """计算MSE（均方误差）"""
    pred = np.array(pred_dist, dtype=np.float64)
    real = np.array(real_dist, dtype=np.float64)
    assert len(pred) == len(real), "预测分布与真实分布长度不匹配"
    return np.mean((pred - real) ** 2)


# ===================== Trie优化方案 (已移除adaptive剪枝) =====================
def PEM_OLH(stage_tries, k, m, g, c, epsilon, N, si_trie):
    """使用Trie优化的OLH算法（不支持自适应剪枝）"""
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))

    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X(stage_tries, i)
        current_trie = stage_tries[i]

        # 始终使用完整的候选集D
        D = construct_D(Ct, k, m, i, g)

        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        if use_file:
            construct_D_file(Ct, k, m, i, g)
            OLH_file(t_X, Ni, c, epsilon, i)
            Ct, OLH_dist = construct_C_file(k, i)
        else:
            class TrieDataAdapter:
                def __init__(self, trie):
                    self.trie = trie
                def get_element_counts(self):
                    return self.trie.get_all_elements()
            EstimateDist_OlH = OLH(TrieDataAdapter(current_trie), Ni, c, epsilon, D)
            Ct, OLH_dist = construct_C(EstimateDist_OlH, k, D)

    if not Ct: Ct = []
    if not OLH_dist: OLH_dist = []
    return Ct, OLH_dist


def PEM_wheel(stage_tries, k, m, g, c, epsilon, N, si_trie):
    """使用Trie优化的Wheel算法（不支持自适应剪枝）"""
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))

    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X(stage_tries, i)
        current_trie = stage_tries[i]

        # 始终使用完整的候选集D
        D = construct_D(Ct, k, m, i, g)

        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        if use_file:
            construct_D_file(Ct, k, m, i, g)
            set_wheel_file(t_X, Ni, c, epsilon, i)
            Ct, wheel_dist = construct_C_file(k, i)
        else:
            class TrieDataAdapter:
                def __init__(self, trie):
                    self.trie = trie
                def get_element_counts(self):
                    return self.trie.get_all_elements()
            EstimateDist_wheel = set_wheel(TrieDataAdapter(current_trie), Ni, c, epsilon, D)
            Ct, wheel_dist = construct_C(EstimateDist_wheel, k, D)

    if not Ct: Ct = []
    if not wheel_dist: wheel_dist = []
    return Ct, wheel_dist


# ===================== 基于上一轮估计频率的自适应剪枝算法 (动态剪枝比例) =====================
def PEM_OLH_est(stage_tries, k, m, g, c, epsilon, N, si_trie, adaptive=False, initial_prune_ratio=0.8,
                final_prune_ratio=0.2):
    """
    使用Trie优化的OLH算法（支持基于上一轮带噪声估计频率的剪枝）
    - initial_prune_ratio: 第二轮的剪枝比例（保留前 initial_prune_ratio 的候选）
    - final_prune_ratio: 最后一轮的剪枝比例（逐渐降低到这个值）
    """
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))  # 初始候选集
    prev_estimates = {}  # 用于存储上一轮 (候选者, 带噪声估计频率) 的字典

    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X(stage_tries, i)
        current_trie = stage_tries[i]

        # 核心修改：根据上一轮的估计频率动态构建候选集 D
        if adaptive and i > 1 and prev_estimates:
            # 从第二轮开始，基于上一轮的带噪声估计频率进行剪枝
            sorted_items = sorted(prev_estimates.items(), key=lambda item: item[1], reverse=True)
            num_candidates = len(sorted_items)

            # 动态计算当前轮次的剪枝比例
            if g - 1 > 0:
                prune_ratio = initial_prune_ratio - (initial_prune_ratio - final_prune_ratio) * (i - 2) / (g - 2)
            else:
                prune_ratio = initial_prune_ratio
            prune_ratio = max(final_prune_ratio, min(initial_prune_ratio, prune_ratio))

            num_to_keep = max(k, int(num_candidates * prune_ratio))
            candidates_to_expand = [item[0] for item in sorted_items[:num_to_keep]]

            # 构建新的候选集 D
            D = []
            sr_curr = math.ceil(math.log2(k)) + math.ceil(i * (m - math.ceil(math.log2(k))) / g)
            sr_prev = math.ceil(math.log2(k)) + math.ceil((i - 1) * (m - math.ceil(math.log2(k))) / g)
            s_len_diff = sr_curr - sr_prev

            for ct_val in candidates_to_expand:
                prefix = ct_val << s_len_diff
                for suffix in range(1 << s_len_diff):
                    D.append(prefix | suffix)
        else:
            # 第一轮或未启用自适应，使用原始方法构建候选集
            D = construct_D(Ct, k, m, i, g)

        # 后续逻辑与原 PEM_OLH 基本保持不变
        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        if use_file:
            # 文件处理逻辑保持不变
            construct_D_file(Ct, k, m, i, g)
            OLH_file(t_X, Ni, c, epsilon, i)
            Ct, OLH_dist = construct_C_file(k, i)
        else:
            class TrieDataAdapter:
                def __init__(self, trie):
                    self.trie = trie
                def get_element_counts(self):
                    return self.trie.get_all_elements()
            EstimateDist_OlH = OLH(TrieDataAdapter(current_trie), Ni, c, epsilon, D)
            Ct, OLH_dist = construct_C(EstimateDist_OlH, k, D)

        # 更新上一轮的估计频率字典
        if i > 0 and Ct and OLH_dist:
            prev_estimates = dict(zip(Ct, OLH_dist))

    if not Ct: Ct = []
    if not OLH_dist: OLH_dist = []
    return Ct, OLH_dist


def PEM_wheel_est(stage_tries, k, m, g, c, epsilon, N, si_trie, adaptive=False, initial_prune_ratio=0.8,
                  final_prune_ratio=0.2):
    """
    使用Trie优化的Wheel算法（支持基于上一轮带噪声估计频率的剪枝）
    - initial_prune_ratio: 第二轮的剪枝比例（保留前 initial_prune_ratio 的候选）
    - final_prune_ratio: 最后一轮的剪枝比例（逐渐降低到这个值）
    """
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))  # 初始候选集
    prev_estimates = {}  # 用于存储上一轮 (候选者, 带噪声估计频率) 的字典

    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X(stage_tries, i)
        current_trie = stage_tries[i]

        # 核心修改：根据上一轮的估计频率动态构建候选集 D
        if adaptive and i > 1 and prev_estimates:
            sorted_items = sorted(prev_estimates.items(), key=lambda item: item[1], reverse=True)
            num_candidates = len(sorted_items)

            # 动态计算当前轮次的剪枝比例
            if g - 1 > 0:
                prune_ratio = initial_prune_ratio - (initial_prune_ratio - final_prune_ratio) * (i - 2) / (g - 2)
            else:
                prune_ratio = initial_prune_ratio
            prune_ratio = max(final_prune_ratio, min(initial_prune_ratio, prune_ratio))

            num_to_keep = max(k, int(num_candidates * prune_ratio))
            candidates_to_expand = [item[0] for item in sorted_items[:num_to_keep]]

            # 构建新的候选集 D
            D = []
            sr_curr = math.ceil(math.log2(k)) + math.ceil(i * (m - math.ceil(math.log2(k))) / g)
            sr_prev = math.ceil(math.log2(k)) + math.ceil((i - 1) * (m - math.ceil(math.log2(k))) / g)
            s_len_diff = sr_curr - sr_prev

            for ct_val in candidates_to_expand:
                prefix = ct_val << s_len_diff
                for suffix in range(1 << s_len_diff):
                    D.append(prefix | suffix)
        else:
            # 第一轮或未启用自适应，使用原始方法构建候选集
            D = construct_D(Ct, k, m, i, g)

        # 后续逻辑与原 PEM_wheel 基本保持不变
        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        if use_file:
            # 文件处理逻辑保持不变
            construct_D_file(Ct, k, m, i, g)
            set_wheel_file(t_X, Ni, c, epsilon, i)
            Ct, wheel_dist = construct_C_file(k, i)
        else:
            class TrieDataAdapter:
                def __init__(self, trie):
                    self.trie = trie
                def get_element_counts(self):
                    return self.trie.get_all_elements()
            EstimateDist_wheel = set_wheel(TrieDataAdapter(current_trie), Ni, c, epsilon, D)
            Ct, wheel_dist = construct_C(EstimateDist_wheel, k, D)

        # 更新上一轮的估计频率字典
        if i > 0 and Ct and wheel_dist:
            prev_estimates = dict(zip(Ct, wheel_dist))

    if not Ct: Ct = []
    if not wheel_dist: wheel_dist = []
    return Ct, wheel_dist


# ===================== 结果可视化 =====================
def plot_model_comparison(epsilon_values, all_results):
    """绘制模型对比图（含F1、NCR、MSE）"""
    plt.figure(figsize=(18, 6))
    model_avg = {
        'f1': {},
        'ncr': {},
        'mse': {}
    }

    for model in all_results:
        model_avg['f1'][model] = np.mean(all_results[model]['f1'], axis=0)
        model_avg['ncr'][model] = np.mean(all_results[model]['ncr'], axis=0)
        model_avg['mse'][model] = np.mean(all_results[model]['mse'], axis=0)

    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p']
    colors = ['blue', 'green', 'red', 'purple', 'orange', 'cyan', 'magenta', 'brown']

    plt.subplot(1, 3, 1)
    idx = 0
    for model_name in model_avg['f1']:
        plt.plot(epsilon_values, model_avg['f1'][model_name],
                 marker=markers[idx % len(markers)],
                 color=colors[idx % len(colors)],
                 label=model_name, linewidth=2, markersize=6)
        idx += 1
    plt.xlabel('Epsilon', fontsize=10)
    plt.ylabel('Average F1-Score', fontsize=10)
    plt.title('F1-Score Comparison Across Models', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.subplot(1, 3, 2)
    idx = 0
    for model_name in model_avg['ncr']:
        plt.plot(epsilon_values, model_avg['ncr'][model_name],
                 marker=markers[idx % len(markers)],
                 color=colors[idx % len(colors)],
                 label=model_name, linewidth=2, markersize=6)
        idx += 1
    plt.xlabel('Epsilon', fontsize=10)
    plt.ylabel('Average NCR', fontsize=10)
    plt.title('NCR Comparison Across Models', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.subplot(1, 3, 3)
    idx = 0
    for model_name in model_avg['mse']:
        plt.plot(epsilon_values, model_avg['mse'][model_name],
                 marker=markers[idx % len(markers)],
                 color=colors[idx % len(colors)],
                 label=model_name, linewidth=2, markersize=6)
        idx += 1
    plt.yscale('log')
    plt.xlabel('Epsilon', fontsize=10)
    plt.ylabel('Average MSE', fontsize=10)
    plt.title('MSE Comparison Across Models', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.tight_layout()
    plt.show()
    return model_avg


def _build_candidate_set_adaptive(Ct, prev_estimates, i, k, m, g, adaptive, initial_prune_ratio, final_prune_ratio):
    """按轮次构造候选集，并返回候选集与当前轮次剪枝比例。"""
    if adaptive and i > 1 and prev_estimates:
        sorted_items = sorted(prev_estimates.items(), key=lambda item: item[1], reverse=True)
        num_candidates = len(sorted_items)

        if g > 2:
            prune_ratio = initial_prune_ratio - (initial_prune_ratio - final_prune_ratio) * (i - 2) / (g - 2)
        else:
            prune_ratio = initial_prune_ratio
        prune_ratio = max(final_prune_ratio, min(initial_prune_ratio, prune_ratio))

        num_to_keep = max(k, int(num_candidates * prune_ratio))
        candidates_to_expand = [item[0] for item in sorted_items[:num_to_keep]]

        D = []
        sr_curr = math.ceil(math.log2(k)) + math.ceil(i * (m - math.ceil(math.log2(k))) / g)
        sr_prev = math.ceil(math.log2(k)) + math.ceil((i - 1) * (m - math.ceil(math.log2(k))) / g)
        s_len_diff = sr_curr - sr_prev

        for ct_val in candidates_to_expand:
            prefix = ct_val << s_len_diff
            for suffix in range(1 << s_len_diff):
                D.append(prefix | suffix)

        return D, prune_ratio

    return construct_D(Ct, k, m, i, g), 1.0


def profile_pe_method(stage_tries, k, m, g, c, epsilon, method='olh', adaptive=False,
                      initial_prune_ratio=0.8, final_prune_ratio=0.2):
    """带统计信息执行算法，返回每轮候选规模/内存/耗时及总耗时。"""
    S0 = math.ceil(math.log2(k))
    Ct = list(range(0, 1 << S0))
    prev_estimates = {}
    round_stats = {
        'candidate_size': [],
        'memory_mb': [],
        'round_runtime_s': [],
        'prune_ratio': []
    }

    process = psutil.Process()
    for i in range(1, g + 1):
        t_X, Ni = split_prefix_X(stage_tries, i)
        current_trie = stage_tries[i]

        D, prune_ratio = _build_candidate_set_adaptive(
            Ct, prev_estimates, i, k, m, g, adaptive, initial_prune_ratio, final_prune_ratio
        )

        round_stats['candidate_size'].append(len(D))
        round_stats['prune_ratio'].append(prune_ratio)
        round_stats['memory_mb'].append(process.memory_info().rss / (1024 ** 2))

        estimated_memory = len(D) * 8 / (1024 ** 2)
        use_file = estimated_memory > get_available_memory() * 0.3

        round_t0 = time.perf_counter()

        if use_file:
            construct_D_file(Ct, k, m, i, g)
            if method == 'olh':
                OLH_file(t_X, Ni, c, epsilon, i)
            else:
                set_wheel_file(t_X, Ni, c, epsilon, i)
            Ct, dist = construct_C_file(k, i)
        else:
            class TrieDataAdapter:
                def __init__(self, trie):
                    self.trie = trie

                def get_element_counts(self):
                    return self.trie.get_all_elements()

            if method == 'olh':
                est = OLH(TrieDataAdapter(current_trie), Ni, c, epsilon, D)
            else:
                est = set_wheel(TrieDataAdapter(current_trie), Ni, c, epsilon, D)
            Ct, dist = construct_C(est, k, D)

        round_t1 = time.perf_counter()
        round_stats['round_runtime_s'].append(max(0.0, round_t1 - round_t0))

        if Ct and dist:
            prev_estimates = dict(zip(Ct, dist))

    round_stats['total_runtime_s'] = sum(round_stats['round_runtime_s'])
    return Ct, dist, round_stats


def plot_runtime_vs_n(dataset_name, runtime_results, output_path):
    """绘制 Runtime vs N 曲线图。"""
    plt.figure(figsize=(8, 5))
    for model_name, points in runtime_results.items():
        x_vals = [x for x, _ in points]
        y_vals = [y for _, y in points]
        plt.plot(x_vals, y_vals, marker='o', linewidth=2, label=model_name)

    plt.xlabel('N (number of users)')
    plt.ylabel('Runtime (seconds)')
    plt.title(f'Runtime vs N ({dataset_name})')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_round_curve(dataset_name, round_results, metric_key, ylabel, title, output_path, log_scale=False):
    """绘制按轮次变化曲线（Memory / Candidate Size）。"""
    plt.figure(figsize=(8, 5))
    for model_name, stat in round_results.items():
        rounds = list(range(1, len(stat[metric_key]) + 1))
        plt.plot(rounds, stat[metric_key], marker='o', linewidth=2, label=model_name)

    if log_scale:
        plt.yscale('log')

    plt.xlabel('Round g')
    plt.ylabel(ylabel)
    plt.title(f'{title} ({dataset_name})')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def run_efficiency_analysis(dataset_name, file_name, m, k, g, c, epsilon,
                            n_values, initial_prune_ratio, final_prune_ratio,
                            output_dir='../../result/efficiency'):
    """输出三类效率验证曲线：Runtime vs N / Memory vs Round / Candidate Size vs Round。"""
    import os
    import time

    if not os.path.exists(file_name):
        print(f"[Skip] 数据集不存在，跳过效率分析: {file_name}")
        return

    os.makedirs(output_dir, exist_ok=True)
    X, _, _, N_full, c_data = read_data(file_name, k)
    c_eff = c if c is not None else c_data

    runtime_results = {
        'PEM_OLH': [],
        'PEM_Wheel': [],
        'A-HPEM': []
    }

    for n_target in n_values:
        n_eff = min(n_target, N_full)
        X_sub = X[:n_eff]
        stage_tries, si_trie = data_to_prefix_t(X_sub, n_eff, g, c_eff, m, k)

        t0 = time.perf_counter()
        profile_pe_method(stage_tries, k, m, g, c_eff, epsilon, method='olh', adaptive=False)
        runtime_results['PEM_OLH'].append((n_eff, time.perf_counter() - t0))

        t0 = time.perf_counter()
        profile_pe_method(stage_tries, k, m, g, c_eff, epsilon, method='wheel', adaptive=False)
        runtime_results['PEM_Wheel'].append((n_eff, time.perf_counter() - t0))

        t0 = time.perf_counter()
        profile_pe_method(stage_tries, k, m, g, c_eff, epsilon, method='wheel', adaptive=True,
                          initial_prune_ratio=initial_prune_ratio, final_prune_ratio=final_prune_ratio)
        runtime_results['A-HPEM'].append((n_eff, time.perf_counter() - t0))

        print(f"[{dataset_name}] Runtime benchmark done: N={n_eff}")

    largest_n = min(max(n_values), N_full)
    X_sub = X[:largest_n]
    stage_tries, si_trie = data_to_prefix_t(X_sub, largest_n, g, c_eff, m, k)

    _, _, olh_round = profile_pe_method(stage_tries, k, m, g, c_eff, epsilon, method='olh', adaptive=False)
    _, _, wheel_round = profile_pe_method(stage_tries, k, m, g, c_eff, epsilon, method='wheel', adaptive=False)
    _, _, ahpem_round = profile_pe_method(stage_tries, k, m, g, c_eff, epsilon, method='wheel', adaptive=True,
                                          initial_prune_ratio=initial_prune_ratio,
                                          final_prune_ratio=final_prune_ratio)

    round_results = {
        'PEM_OLH': olh_round,
        'PEM_Wheel': wheel_round,
        'A-HPEM': ahpem_round,
    }

    runtime_path = os.path.join(output_dir, f'{dataset_name}_runtime_vs_n.png')
    memory_path = os.path.join(output_dir, f'{dataset_name}_memory_vs_round.png')
    candidate_path = os.path.join(output_dir, f'{dataset_name}_candidate_vs_round.png')

    plot_runtime_vs_n(dataset_name, runtime_results, runtime_path)
    plot_round_curve(dataset_name, round_results, 'memory_mb', 'Memory (MB)', 'Memory vs Round', memory_path)
    plot_round_curve(dataset_name, round_results, 'candidate_size', 'Candidate size', 'Candidate Size vs Round',
                     candidate_path, log_scale=True)

    print(f"[Done] 效率曲线已保存: {runtime_path}")
    print(f"[Done] 效率曲线已保存: {memory_path}")
    print(f"[Done] 效率曲线已保存: {candidate_path}")


if __name__ == '__main__':
    import os

    # 配置参数
    m = 64
    k = 16
    g = 32
    file_name = '../../data/synthetic_data/64_15.txt'

    # 动态剪枝比例参数
    initial_prune_ratio = 0.7
    final_prune_ratio = 0.3

    # 读取数据
    X, Real_k_dist, Real_k_data, N, c = read_data(file_name, k)
    c = 10

    print("=== 真实数据信息 ===")
    print("真实Top-k数据:", Real_k_data)
    print("真实Top-k频率:", [round(d, 4) for d in Real_k_dist])

    # 生成前缀 (Trie优化方案)
    stage_tries, si_trie = data_to_prefix_t(X, N, g, c, m, k)

    # 原方案生成前缀
    prefix_X, si = data_to_prefix(X, N, g, c, m, k)

    # 结果文件配置
    model_files = {
        'OLH': {'f1': '../../result/synthetic/epsilon/f1_olh.txt', 'ncr': '../../result/synthetic/epsilon/ncr_olh.txt',
                'mse': '../../result/synthetic/epsilon/mse_olh.txt'},
        'Wheel': {'f1': '../../result/synthetic/epsilon/f1_wheel.txt',
                  'ncr': '../../result/synthetic/epsilon/ncr_wheel.txt',
                  'mse': '../../result/synthetic/epsilon/mse_wheel.txt'},
        'Adaptive_Hybrid': {'f1': '../../result/synthetic/epsilon/f1_adaptive_hybrid.txt',
                            'ncr': '../../result/synthetic/epsilon/ncr_adaptive_hybrid.txt',
                            'mse': '../../result/synthetic/epsilon/mse_adaptive_hybrid.txt'},
    }

    # 初始化所有结果文件
    for model in model_files.values():
        for f in model.values():
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f, 'w') as file:
                file.write('')

    # 实验配置
    t_num = 5
    num_epsilons = 10
    epsilon_values = []
    all_results = {
        'OLH': {'f1': [], 'ncr': [], 'mse': []},
        'Wheel': {'f1': [], 'ncr': [], 'mse': []},
        'Adaptive_Hybrid': {'f1': [], 'ncr': [], 'mse': []},
    }

    # 运行实验
    for t_num_i in range(t_num):
        print(f"\n=== 重复实验 {t_num_i + 1}/{t_num} ===")

        results = {
            'OLH': {'f1': [0.0] * num_epsilons, 'ncr': [0.0] * num_epsilons, 'mse': [0.0] * num_epsilons},
            'Wheel': {'f1': [0.0] * num_epsilons, 'ncr': [0.0] * num_epsilons, 'mse': [0.0] * num_epsilons},
            'Adaptive_Hybrid': {'f1': [0.0] * num_epsilons, 'ncr': [0.0] * num_epsilons, 'mse': [0.0] * num_epsilons},
        }

        for i in range(num_epsilons):
            epsilon = (i + 1) * 0.5
            if t_num_i == 0:
                epsilon_values.append(epsilon)
            print(f"\n--- 处理 epsilon = {epsilon} ---")

            # 1. OLH（不带剪枝）
            ct, dist = PEM_OLH_nt(prefix_X, k, m, g, c, epsilon, N, si)
            results['OLH']['f1'][i] = cal_f1(Real_k_data, ct)
            results['OLH']['ncr'][i] = cal_ncr(Real_k_data, ct, Real_k_dist, dist, k)
            results['OLH']['mse'][i] = cal_mse(dist, Real_k_dist)
            print(
                f"OLH - F1={results['OLH']['f1'][i]:.4f}, NCR={results['OLH']['ncr'][i]:.4f}, MSE={results['OLH']['mse'][i]:.2e}")

            # 2. Wheel（不带剪枝）
            ct, dist = PEM_wheel_nt(prefix_X, k, m, g, c, epsilon, N, si)
            results['Wheel']['f1'][i] = cal_f1(Real_k_data, ct)
            results['Wheel']['ncr'][i] = cal_ncr(Real_k_data, ct, Real_k_dist, dist, k)
            results['Wheel']['mse'][i] = cal_mse(dist, Real_k_dist)
            print(
                f"Wheel - F1={results['Wheel']['f1'][i]:.4f}, NCR={results['Wheel']['ncr'][i]:.4f}, MSE={results['Wheel']['mse'][i]:.2e}")

            # 3. Adaptive_Hybrid（基于上一轮估计频率的剪枝）
            if epsilon < 1:
                ct_hybrid, dist_hybrid = PEM_OLH_est(stage_tries, k, m, g, c, epsilon, N, si_trie, adaptive=True,
                                                     initial_prune_ratio=initial_prune_ratio,
                                                     final_prune_ratio=final_prune_ratio)
                print(f"Adaptive_Hybrid (OLH_est) - epsilon={epsilon} < 1")
            else:
                ct_hybrid, dist_hybrid = PEM_wheel_est(stage_tries, k, m, g, c, epsilon, N, si_trie, adaptive=True,
                                                       initial_prune_ratio=initial_prune_ratio,
                                                       final_prune_ratio=final_prune_ratio)
                print(f"Adaptive_Hybrid (Wheel_est) - epsilon={epsilon} >= 1")
            results['Adaptive_Hybrid']['f1'][i] = cal_f1(Real_k_data, ct_hybrid)
            results['Adaptive_Hybrid']['ncr'][i] = cal_ncr(Real_k_data, ct_hybrid, Real_k_dist, dist_hybrid, k)
            results['Adaptive_Hybrid']['mse'][i] = cal_mse(dist_hybrid, Real_k_dist)
            print(
                f"Adaptive_Hybrid - F1={results['Adaptive_Hybrid']['f1'][i]:.4f}, NCR={results['Adaptive_Hybrid']['ncr'][i]:.4f}, MSE={results['Adaptive_Hybrid']['mse'][i]:.2e}")

        # 保存结果到文件
        for model in model_files:
            with open(model_files[model]['f1'], 'a') as f:
                f.write(' '.join(map(lambda x: f'{x:.4f}', results[model]['f1'])) + '\n')
            with open(model_files[model]['ncr'], 'a') as f:
                f.write(' '.join(map(lambda x: f'{x:.4f}', results[model]['ncr'])) + '\n')
            with open(model_files[model]['mse'], 'a') as f:
                f.write(' '.join(map(lambda x: f'{x:.2e}', results[model]['mse'])) + '\n')

        # 累积结果
        for model in all_results:
            all_results[model]['f1'].append(results[model]['f1'])
            all_results[model]['ncr'].append(results[model]['ncr'])
            all_results[model]['mse'].append(results[model]['mse'])

    # 绘图并输出平均结果
    model_avg = plot_model_comparison(epsilon_values, all_results)
    print("\n=== 模型平均结果对比 ===")
    print(f"Epsilon值: {[round(eps, 1) for eps in epsilon_values]}")

    print("\n1. F1-score平均值:")
    for model in all_results:
        print(f"{model:18} {[round(s, 4) for s in model_avg['f1'][model]]}")

    print("\n2. NCR平均值:")
    for model in all_results:
        print(f"{model:18} {[round(s, 4) for s in model_avg['ncr'][model]]}")

    print("\n3. MSE平均值（科学计数法）:")
    for model in all_results:
        print(f"{model:18} {[f'{s:.2e}' for s in model_avg['mse'][model]]}")

    # 新增：效率验证曲线（Runtime/Memory/Candidate）
    efficiency_datasets = {
        'synthetic': '../../data/synthetic_data/64_15.txt',
        'url': '../../data/url_data/url.txt',
    }
    n_values = [10 ** 4, 5 * 10 ** 4, 10 ** 5, 5 * 10 ** 5, 10 ** 6]
    efficiency_epsilon = 1.0

    for dataset_name, dataset_path in efficiency_datasets.items():
        run_efficiency_analysis(
            dataset_name=dataset_name,
            file_name=dataset_path,
            m=m,
            k=k,
            g=g,
            c=c,
            epsilon=efficiency_epsilon,
            n_values=n_values,
            initial_prune_ratio=initial_prune_ratio,
            final_prune_ratio=final_prune_ratio,
            output_dir='../../result/efficiency'
        )
