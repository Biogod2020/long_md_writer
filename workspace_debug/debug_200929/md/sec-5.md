# The Horizontal Plane: Precordial Leads V1–V6

# 水平面：胸前导联 V1–V6 (The Horizontal Plane: Precordial Leads V1–V6)

在前几节中，我们通过肢体导联构建了心脏在**额面（Frontal Plane）**上的六轴参考系统 [REF:sec-4]。然而，心脏是一个在三维空间中搏动的器官。如果我们只观察额面，就像是只从正前方拍摄一个舞者，我们能看到他向上跃起或向侧面移动，却无法察觉他是在向前靠近观众还是在向后退缩。

为了填补这一空间维度的缺失，我们需要将“摄像机”布置在心脏的水平切面上。这就是**胸前导联（Precordial Leads, V1–V6）**的物理使命：捕捉心脏在**水平面（Horizontal/Transverse Plane）**上的电活动投影。

## 物理架构：单极探查与虚拟地线

与肢体导联不同，胸前导联全部属于**单极导联（Unipolar Leads）**。根据我们在 [REF:sec-3] 中探讨的物理原理，单极导联需要一个稳定的“零电位”作为参考。

胸前导联系统直接采用了**威尔逊中心端（WCT）**作为负极。这意味着，当我们将电极放置在胸壁的特定位置时，心电图机测量的是该点相对于心脏电学中心的电位差。

:::important
**水平面导联轴的定义**
胸前导联的导联轴是从身体中心（WCT）指向胸壁电极位置的径向线段。这六个导联像一把张开的扇子，环绕着心脏的解剖位置，提供了从右前方到左侧方的连续视角。
:::

## 解剖定位：精确的“机位”布置

为了确保临床诊断的可重复性，V1–V6 电极的放置遵循严格的解剖标志：

1.  **V1**：胸骨右缘第 4 肋间。
2.  **V2**：胸骨左缘第 4 肋间。
3.  **V3**：V2 与 V4 连线的中点。
4.  **V4**：左锁骨中线与第 5 肋间相交处。
5.  **V5**：左腋前线，与 V4 水平高度一致。
6.  **V6**：左腋中线，与 V4 水平高度一致。

从物理角度看，V1 和 V2 靠近心脏的右侧和间隔部；V3 和 V4 位于前壁；V5 和 V6 则贴近左心室的侧壁。

## 矢量投影：水平面的 3D 模拟

在水平面坐标系中，我们通常将患者的背部定义为后方，胸骨定义为前方。正常心室除极的总向量 $\vec{P}$ 在水平面上不仅向左，而且由于左心室位于解剖位置的后侧，向量还会稍向后倾斜。

下方的 SVG 模拟器展示了心脏除极向量在水平面六个导联轴上的投影过程。

<figure>
    <div class="flex justify-center bg-slate-50/50 rounded-lg p-8 border border-slate-200">
        <svg viewBox="0 0 500 400" class="w-full max-w-xl">
            <!-- Chest Cross-section Outline -->
            <path d="M 100 200 Q 100 100 250 100 Q 400 100 400 200 Q 400 350 250 350 Q 100 350 100 200" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4" />
            
            <!-- Heart in the Center -->
            <path d="M 230 200 Q 250 170 270 200 Q 250 250 230 200" fill="#e11d48" opacity="0.2" />
            <circle cx="250" cy="200" r="5" fill="#0ea5e9" /> <!-- WCT Center -->
            <text x="250" y="190" class="font-sans text-[10px] fill-medical-600" text-anchor="middle">WCT</text>

            <!-- Precordial Lead Axes -->
            <g stroke="#0c4a6e" stroke-width="1.5" stroke-dasharray="2">
                <!-- V1: ~115 deg -->
                <line x1="250" y1="200" x2="330" y2="130" />
                <circle cx="330" cy="130" r="4" fill="#0ea5e9" />
                <text x="340" y="125" class="font-sans text-xs font-bold fill-medical-900">V1</text>

                <!-- V2: ~90 deg -->
                <line x1="250" y1="200" x2="250" y2="110" />
                <circle cx="250" cy="110" r="4" fill="#0ea5e9" />
                <text x="250" y="100" class="font-sans text-xs font-bold fill-medical-900" text-anchor="middle">V2</text>

                <!-- V4: ~30 deg -->
                <line x1="250" y1="200" x2="130" y2="150" />
                <circle cx="130" cy="150" r="4" fill="#0ea5e9" />
                <text x="120" y="145" class="font-sans text-xs font-bold fill-medical-900">V4</text>

                <!-- V6: ~0 deg -->
                <line x1="250" y1="200" x2="110" y2="200" />
                <circle cx="110" cy="200" r="4" fill="#0ea5e9" />
                <text x="100" y="205" class="font-sans text-xs font-bold fill-medical-900" text-anchor="end">V6</text>
            </g>

            <!-- Main Depolarization Vector P -->
            <line x1="250" y1="200" x2="160" y2="240" stroke="#e11d48" stroke-width="4" marker-end="url(#vectorArrow)" />
            <text x="150" y="260" class="font-serif italic text-sm fill-heart-red">Mean Vector P</text>

            <!-- Marker Definition -->
            <defs>
                <marker id="vectorArrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#e11d48" />
                </marker>
            </defs>
            
            <text x="250" y="380" class="font-sans text-xs fill-slate-400" text-anchor="middle">水平面 (Horizontal Plane) 投影视图</text>
        </svg>
    </div>
    <figcaption>图 2-5: 胸前导联的水平面分布。注意总除极向量 P 如何从 V1（右前）指向 V6（左侧）。</figcaption>
</figure>

## 核心物理现象：R 波递增 (R-wave Progression)

在胸前导联中，最显著的物理特征是 **R 波振幅从 V1 到 V5/V6 的逐渐增加**，以及相应的 S 波逐渐变浅。这一现象并非偶然，而是心脏除极顺序在水平面投影的直接推论。

### 1. V1 和 V2：间隔视角
在除极初期，室间隔的除极方向是从左向右的。由于 V1 位于右侧，它首先会看到一个微小的正向波（r 波）。随后，强大的左心室除极开始，主向量向左、向后撤离 V1。
- **物理结果**：根据 $V = |\vec{P}| \cos(\theta)$，当 $\theta > 90^\circ$ 时，$V$ 为负值。因此 V1 记录到一个深大的负向波（S 波）。

### 2. V3 和 V4：移行区 (Transition Zone)
随着电极向左移动，导联轴与主向量 $\vec{P}$ 的夹角逐渐减小。在 V3 或 V4 附近，主向量的方向几乎垂直于导联轴。
- **物理结果**：此时 R 波与 S 波的振幅大致相等（$R/S \approx 1$）。这在临床上被称为“移行区”。

### 3. V5 和 V6：左室视角
V5 和 V6 的导联轴几乎与左心室的主除极方向平行。
- **物理结果**：$\cos(\theta)$ 趋近于 1，产生高大的正向 R 波，而 S 波几乎消失。

:::important
**R 波递增的物理法则**
正常的 R 波递增反映了左心室在水平面上的主导地位。如果 V1 到 V6 的 R 波始终低平（Poor R-wave Progression），物理上意味着心脏前壁的电向量消失，这通常是前壁心肌梗死的强有力证据。
:::

## 临床物理：导联组与解剖区域的对应

胸前导联将心脏划分为不同的电生理“监控区”，这对于心肌梗死的定位至关重要：

| 导联组 | 观察区域 | 对应的主要冠状动脉 |
| :--- | :--- | :--- |
| **V1, V2** | 室间隔 (Septal) | LAD (前降支) 间隔支 |
| **V3, V4** | 前壁 (Anterior) | LAD (前降支) 主体 |
| **V5, V6** | 低侧壁 (Lateral) | LCX (回旋支) 或 LAD 远端 |


![Image Placeholder: Anatomical Cross-section of the Heart matching V1-V6 leads](https://via.placeholder.com/800x450/f8fafc/0c4a6e?text=Anatomical+Correlation+of+Precordial+Leads)


## 物理陷阱：导联位置的高度敏感性

由于胸前电极距离心脏极近（处于“近场”观测），电极位置的微小垂直移动都会显著改变投影角度。

:::warning
**病理伪像：V1/V2 位置过高**
如果将 V1/V2 电极放置在第 2 肋间而非第 4 肋间，导联轴将从上方俯视心底部。这可能导致 P 波倒置或出现类似右束支传导阻滞（RBBB）的波形，这种由于物理机位错误导致的“假性病理”在临床中屡见不鲜。
:::

## 总结

胸前导联 V1–V6 的引入，完成了我们将心脏从二维照片还原为三维模型的最后一步。
- **肢体导联 [REF:sec-2, sec-3]** 负责额面的纵向切割。
- **胸前导联** 负责水平面的横向环绕。

至此，12 导联系统已经形成了一个完整的 3D 空间采样阵列。在下一节中，我们将回归数学本质，深入探讨**点积物理学（Dot Product Physics）**如何决定每一条波形的细微形态，以及如何通过这些数学规律推导出复杂的心律失常表现 [REF:sec-6]。

---

<div class="flex justify-between items-center mt-12 p-6 bg-slate-50 rounded-xl border border-slate-200">
    <div>
        <span class="text-xs font-mono text-slate-400 uppercase tracking-widest">Next Section</span>
        <h4 class="m-0 text-medical-700">The Physics of Projection: Dot Products and Wave Morphology</h4>
    </div>
    <a href="#sec-6" class="text-medical-500 hover:text-medical-600">
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
    </a>
</div>