<script setup>
// ==================== Vue 相关导入 ====================
import { ref, onBeforeUnmount, computed, onMounted, watch, nextTick, markRaw } from 'vue'
// ECharts 图表库
import * as echarts from 'echarts'
// Element Plus 组件
import { ElPopover, ElButton, ElMessage, ElMessageBox, ElRow, ElCol, ElStatistic, ElIcon, ElDivider, ElSwitch, ElSlider } from 'element-plus'
// VueUse 工具库
import { useTransition } from '@vueuse/core'
// Element Plus 图标
import { InfoFilled, Eleme, DataAnalysis, Download, Delete, Upload, Sunny } from '@element-plus/icons-vue'

// 使用 markRaw 包装图标组件以避免 Vue 响应式代理问题
const DataAnalysisIcon = markRaw(DataAnalysis)

// ==================== 静态资源配置 ====================
// 组件图片路径
const transformer_image_path = 'image/transformer.png'
const user_image_path = 'image/user.png'
const switch_image_path = 'image/switch.png'
const transformer_image_path2 = 'image/transformer2.png'
// 用户类型图标路径（拖出后根据类型显示）
const jumindi_image_path = 'image/jumindi.png'
const shangchang_image_path = 'image/shangchang.png'
const huagongchang_image_path = 'image/huagongchang.png'
// 后端 API 基础 URL（生产环境使用相对路径，开发环境通过 vite proxy 代理）
const backend_base_url = ''

// ==================== 画布状态 ====================
// 画布 DOM 引用
const canvasRef = ref(null)
// 画布上的所有组件（变压器、用户、开关）
const clones = ref([])
// 下一个组件 ID（自增）
let nextId = 1
// 当前正在拖拽的组件状态
const dragging = ref(null)

// 画布拖动状态（整体移动所有组件）
const canvasDrag = ref({
  active: false,      // 是否正在拖动
  startX: 0,          // 拖动起始 X 坐标
  startY: 0,          // 拖动起始 Y 坐标
  startClones: [],    // 拖动开始时的组件位置
  startLines: [],     // 拖动开始时的连线位置
})

// ==================== 右键菜单状态 ====================
// 组件右键菜单
const contextMenu = ref({
  visible: false,     // 是否显示
  x: 0,               // 菜单 X 坐标
  y: 0,               // 菜单 Y 坐标
  cloneId: null,      // 当前操作的组件 ID
  virtualRef: null,   // Popover 虚拟引用
})

// ==================== 连线状态 ====================
// 画布上的所有连线
const lines = ref([])
// 下一条连线 ID（自增）
let nextLineId = 1

// 连线绘制状态
const linking = ref({
  active: false,      // 是否正在连线
  fromId: null,       // 连线起点组件 ID
  x: 0,               // 鼠标当前 X 坐标
  y: 0,               // 鼠标当前 Y 坐标
})

// 连线右键菜单
const lineMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  lineId: null,
  virtualRef: null,
})

// ==================== 计算属性 ====================
// 组件右键菜单标题
const contextMenuTitle = computed(() => {
  if (contextMenu.value.cloneId == null) return ''
  const clone = clones.value.find(c => c.id === contextMenu.value.cloneId)
  return clone?.name || ''
})

// 连线右键菜单标题
const lineMenuTitle = computed(() => {
  if (lineMenu.value.lineId == null) return ''
  const line = lines.value.find(l => l.id === lineMenu.value.lineId)
  return line?.name || ''
})

// ==================== 参数编辑器状态 ====================
const paramEditor = ref({
  targetType: null,           // 编辑目标类型（node/wire）
  targetId: null,             // 编辑目标 ID
  nodeType: null,             // 节点类型（transformer/user/switch）
  name: '',                   // 名称
  voltage: '',                // 电压
  current: '',                // 电流
  power: '',                  // 功率
  demandPower: '',            // 需求功率
  maxPowerKw: '',             // 铭牌容量
  maxActivePowerKw: '',       // 最大有功功率 (kW) = 铭牌容量 × 0.8
  currentPowerKw: '',         // 当前功率
  lossPowerKw: '',            // 损耗功率
  switchLinks: [],            // 开关连接的变压器列表
  status: 'normal',           // 状态
  aiAnswer: '',               // AI 返回的答案
  virtualRef: null,           // Popover 虚拟引用
  // 用户类型相关字段
  userType: 'residential',    // 用户类型（居民/商业/工业）
  currentLoadProfile: [],     // 当前负荷曲线
  currentTimeSlice: 0,        // 当前时间片
  // 图表初始化标志
  chartReady: false,
})

// ==================== 用户类型配置 ====================
// 用户类型功率范围
const USER_TYPE_RANGES = {
  residential: { min: 0, max: 300, default: 150 },    // 居民用户：0-300kW，默认 150kW
  commercial: { min: 0, max: 600, default: 250 },     // 商业用户：0-600kW，默认 250kW
  industrial: { min: 0, max: 999, default: 800 },     // 工业用户：0-999kW，默认 800kW
}

// 默认负荷曲线（实际功率值，单位 kW）
// 时间点：0:00, 4:00, 8:00, 12:00, 16:00, 20:00
const DEFAULT_LOAD_PROFILES = {
  // 居民用户：50-200kW，早晚双高峰（16:00-20:00 最高）
  residential: [60, 50, 120, 90, 180, 200],
  // 商业用户：20-500kW，白天营业时段高（10:00-16:00 最高）
  commercial: [20, 20, 150, 400, 500, 200],
  // 工业用户：200-800kW，白天持续高负荷（8:00-16:00 最高）
  industrial: [200, 200, 400, 800, 600, 350],
}

// 时间轴标签
const TIME_LABELS = ['0:00', '4:00', '8:00', '12:00', '16:00', '20:00']

// 负荷曲线图表实例
let loadProfileChartInstance = null

// 仿真运行状态
const simulationRunning = ref(false)

// ==================== 响应式缩放配置 ====================
// 基于特定分辨率的缩放配置
// 1920x1080 -> 0.8, 2560x1440 -> 1.0, 3840x2160 -> 1.2
const RESOLUTIONS = [
  { width: 1920, height: 1080, scale: 0.8 },
  { width: 2560, height: 1440, scale: 1.0 },
  { width: 3840, height: 2160, scale: 1.2 },
]
const uiScale = ref(1)

/**
 * 更新 UI 缩放比例
 * 根据屏幕分辨率自动调整界面缩放
 */
const updateUiScale = () => {
  const screenWidth = window.screen.width
  const screenHeight = window.screen.height

  // 查找匹配的分辨率
  for (const res of RESOLUTIONS) {
    if (screenWidth === res.width && screenHeight === res.height) {
      uiScale.value = res.scale
      return
    }
  }

  // 如果分辨率处于中间值，使用线性插值计算缩放比例
  if (screenWidth < 1920) {
    uiScale.value = 0.8
  } else if (screenWidth > 3840) {
    uiScale.value = 1.2
  } else if (screenWidth <= 2560) {
    // 在 1920 和 2560 之间插值
    const ratio = (screenWidth - 1920) / (2560 - 1920)
    uiScale.value = 0.8 + ratio * (1.0 - 0.8)
  } else {
    // 在 2560 和 3840 之间插值
    const ratio = (screenWidth - 2560) / (3840 - 2560)
    uiScale.value = 1.0 + ratio * (1.2 - 1.0)
  }
}

// 图表可见性控制
const chartVisible = ref(false) // 默认为 false，通过 Popover 控制

/**
 * 切换图表显示状态
 */
const toggleChart = () => {
  chartVisible.value = !chartVisible.value
}

// ==================== AI 调度状态 ====================
const aiGlobal = ref({
  running: false,              // 是否正在运行
  progressText: 'AI 正在调度中，请稍候...',  // 进度文本
  lastResult: null,            // 最后一次调度结果
  error: '',                   // 错误信息
  needDispatch: false,         // 是否需要调度
  resultVisible: false,        // AI 结果 Popover 显示状态
})

// ==================== 仿真引擎状态 ====================
const simulationEngine = ref({
  running: false,              // 仿真是否正在运行
  paused: false,               // 仿真是否暂停
  loading: false,              // 仿真调度中（控制按钮加载动画）
  currentTimeSlice: 0,         // 当前时间片（0-5）
  totalSteps: 10,              // 总步数
  currentStep: 0,              // 当前步骤
  delayAfterPlanning: 3000,    // 规划建议后延迟（毫秒）
  phase: 'idle',               // 当前阶段：idle, dispatch, planning, execute, continue
  status: 'stopped',           // 状态：stopped, running, completed
  startTime: null,             // 开始时间
  endTime: null,               // 结束时间
})

// 仿真配置对话框
const simulationConfig = ref({
  visible: false,
  delayAfterPlanning: 3,       // 规划后延迟（秒）
  totalSteps: 10,              // 总步数
})

// ==================== 规划建议状态 ====================
const planningSuggestions = ref({
  loading: false,              // 是否正在加载
  data: null,                  // 建议数据
  error: '',                   // 错误信息
  visible: false,              // 是否可见
})

// 应用建议的状态
const applyingSuggestion = ref({
  active: false,               // 是否正在应用
  index: null,                 // 当前应用的建议索引
  message: '',                 // 提示消息
})

// 已应用的建议索引集合
const appliedSuggestionIndices = ref(new Set())

// ==================== 规划建议计算属性 ====================
// 排序后的建议列表（已应用的移到底部）
const sortedSuggestions = computed(() => {
  const suggestions = planningSuggestions.value.data?.suggestions || []
  if (!suggestions.length) return []

  // 分离未应用和已应用的建议
  const notApplied = []
  const applied = []

  suggestions.forEach((suggestion, originalIndex) => {
    if (appliedSuggestionIndices.value.has(originalIndex)) {
      applied.push({ suggestion, originalIndex, isApplied: true })
    } else {
      notApplied.push({ suggestion, originalIndex, isApplied: false })
    }
  })

  // 返回排序后的列表：未应用的在前，已应用的在后
  return [...notApplied, ...applied]
})

// 未应用的建议数量
const pendingSuggestionsCount = computed(() => {
  const suggestions = planningSuggestions.value.data?.suggestions || []
  return suggestions.length - appliedSuggestionIndices.value.size
})

// 待处理的高优先级数量
const pendingHighPriorityCount = computed(() => {
  const suggestions = planningSuggestions.value.data?.suggestions || []
  return suggestions.filter((s, index) =>
    !appliedSuggestionIndices.value.has(index) && s.priority === 'high'
  ).length
})

// 待处理的中优先级数量
const pendingMediumPriorityCount = computed(() => {
  const suggestions = planningSuggestions.value.data?.suggestions || []
  return suggestions.filter((s, index) =>
    !appliedSuggestionIndices.value.has(index) && s.priority === 'medium'
  ).length
})

// 系统健康度（基于待处理的建议）
const systemHealthStatus = computed(() => {
  if (pendingHighPriorityCount.value > 0) {
    return 'critical'
  } else if (pendingMediumPriorityCount.value > 0) {
    return 'warning'
  }
  return 'good'
})

// 规划建议 Popover ref
const planningPopoverRef = ref(null)

// AI 按钮和结果 Popover 引用
const aiButtonRef = ref()
const aiResultPopoverRef = ref()
const paletteCanvasRef = ref(null)

// ==================== 粒子特效 ====================
/**
 * 初始化粒子特效
 * 在组件栏背景创建动态粒子效果
 */
const initParticles = () => {
  const canvas = paletteCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // 设置 canvas 尺寸为父容器（palette）的尺寸
  const palette = canvas.parentElement
  const updateSize = () => {
    canvas.width = palette.clientWidth
    canvas.height = palette.clientHeight
  }
  updateSize()
  window.addEventListener('resize', updateSize)

  // 粒子配置
  const particleNum = 40      // 粒子数量
  const lineDistance = 80     // 连线距离阈值
  let particles = []
  let interactionParticle = null  // 鼠标交互粒子

  /**
   * 生成随机颜色
   * @returns {string} RGB 颜色字符串
   */
  function getRandomColor() {
    const r = Math.floor(Math.random() * 255)
    const g = Math.floor(Math.random() * 255)
    const b = Math.floor(Math.random() * 255)
    return `${r}, ${g}, ${b}`
  }

  /**
   * 粒子类
   * 表示单个粒子的位置、速度、大小和颜色
   */
  class Particle {
    constructor(x, y, velocityX, velocityY, size, colorRGB) {
      this.x = x
      this.y = y
      this.velocityX = velocityX
      this.velocityY = velocityY
      this.size = size
      this.colorRGB = colorRGB
    }
    
    /** 绘制粒子 */
    draw() {
      ctx.beginPath()
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${this.colorRGB}, ${1 - this.size / 3})`
      ctx.fill()
    }
    
    /** 更新粒子位置 */
    update() {
      // 边界反弹
      if (this.x > canvas.width || this.x < 0) {
        this.velocityX *= -1
      }
      if (this.y > canvas.height || this.y < 0) {
        this.velocityY *= -1
      }
      this.x += this.velocityX
      this.y += this.velocityY
      this.draw()
    }
  }

  /**
   * 生成指定范围内的随机数
   */
  function getRandomArbitrary(min, max) {
    return Math.random() * (max - min) + min
  }

  /** 创建所有粒子 */
  function createParticles() {
    for (let i = 0; i < particleNum; i++) {
      let size = getRandomArbitrary(1, 2) // 减小粒子尺寸
      let x = Math.random() * canvas.width
      let y = Math.random() * canvas.height
      let velocityX = getRandomArbitrary(-0.5, 0.5) // 减慢速度
      let velocityY = getRandomArbitrary(-0.5, 0.5)
      let colorRGB = getRandomColor()
      particles.push(new Particle(x, y, velocityX, velocityY, size, colorRGB))
    }
  }

  /** 绘制粒子之间的连线 */
  function connect() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const p1 = particles[i]
        const p2 = particles[j]
        let distance = Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2))
        if (distance < lineDistance) {
          // 使用其中一个粒子的颜色作为连线颜色
          ctx.strokeStyle = `rgba(${p1.colorRGB}, ${1 - distance / lineDistance})`
          ctx.beginPath()
          ctx.lineWidth = 0.5
          ctx.moveTo(p1.x, p1.y)
          ctx.lineTo(p2.x, p2.y)
          ctx.stroke()
        }
      }
    }
  }

  /** 动画循环 */
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    particles.forEach(particle => particle.update())
    if (interactionParticle) {
      interactionParticle.update()
    }
    connect()
    requestAnimationFrame(animate)
  }

  // 鼠标移出时移除交互粒子
  palette.addEventListener('mouseout', () => {
    if (interactionParticle) {
      particles = particles.filter(p => p !== interactionParticle)
      interactionParticle = null
    }
  })

  // 鼠标移入时创建交互粒子
  palette.addEventListener('mouseover', e => {
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    if (!interactionParticle) {
      const colorRGB = getRandomColor()
      interactionParticle = new Particle(x, y, 0, 0, 2, colorRGB)
      particles.push(interactionParticle)
    }
  })

  // 鼠标移动时更新交互粒子位置
  palette.addEventListener('mousemove', e => {
    if (interactionParticle) {
      const rect = canvas.getBoundingClientRect()
      interactionParticle.x = e.clientX - rect.left
      interactionParticle.y = e.clientY - rect.top
    }
  })

  createParticles()
  animate()
}

/** 切换 AI 结果显示 */
const toggleAiResult = () => {
  aiGlobal.value.resultVisible = !aiGlobal.value.resultVisible
}

// ==================== 清空画布相关 ====================
const clearClicked = ref(false)

const onClearCancel = () => {
  clearClicked.value = false
}

const confirmClear = () => {
  clearAll()
  clearClicked.value = false
}

/** 显示清空确认对话框 */
const confirmClearAction = () => {
  ElMessageBox.confirm('确定清空所有组件和连线吗？', '确认清空', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      confirmClear()
    })
    .catch(() => {
      onClearCancel()
    })
}

// ==================== 图表引用 ====================
const transformerChartRef = ref(null)
const lineChartRef = ref(null)
const totalLoadChartRef = ref(null)
let transformerChartInstance = null
let lineChartInstance = null
let totalLoadChartInstance = null
const lastTransformerChartData = ref({ names: [], current: [], loss: [], backendIds: [] })
const lastLineChartData = ref({ names: [], power: [], lineIds: [] })
// 总负载历史数据（用于绘制曲线）
const totalLoadHistory = ref([])
const selectedCloneId = ref(null)
const selectedLineId = ref(null)
const canvasShapes = ref([])

// 变压器铭牌容量滑块标记 (kVA)
// SCB18-200kVA：铭牌容量范围 100-300 kVA
const transformerPowerMarks = {
  100: '100kVA',
  200: {
    style: {
      color: '#1989FA',
    },
    label: '200kVA',
  },
  300: '300kVA',
}

// SCB14-630kVA：铭牌容量范围 500-700 kVA
const transformer2PowerMarks = {
  500: '500kVA',
  630: {
    style: {
      color: '#1989FA',
    },
    label: '630kVA',
  },
  700: '700kVA',
}

// ==================== 统计数据计算 ====================
/**
 * 计算画布上的统计数据
 * 包括总最大功率、总当前功率、总损耗功率、总需求功率
 */
const stats = computed(() => {
  let maxTotalKw = 0          // 铭牌容量总和 (kVA)
  let maxActiveTotalKw = 0   // 总有功功率 (kW) = 所有变压器的 maxActivePowerKw 之和
  let currentTotalKw = 0    // 总输出功率 (kW) = 所有变压器的 currentPowerKw 之和
  let lossTotalKw = 0
  let demandKw = 0

  if (!clones.value) {
    return {
      maxTotalKw,
      maxActiveTotalKw,
      currentTotalKw,
      lossTotalKw,
      demandKw,
    }
  }

  // 获取当前时间片对应的 loadProfile 索引
  const currentTimeSlice = simulationEngine.value.currentTimeSlice || 0
  const profileIndex = currentTimeSlice % 6

  clones.value.forEach(c => {
    if (c.type === 'transformer' || c.type === 'transformer2') {
      const currentPower = Number(c.currentPowerKw) || 0
      const lossPower = Number(c.lossPowerKw) || 0
      const maxActivePower = Number(c.maxActivePowerKw) || 0

      maxTotalKw += Number(c.maxPowerKw) || 0
      maxActiveTotalKw += maxActivePower
      currentTotalKw += currentPower
      lossTotalKw += lossPower
    } else if (c.type === 'user') {
      // 从 loadProfile 获取当前时刻的功率值
      const loadProfile = c.loadProfile || DEFAULT_LOAD_PROFILES[c.userType] || DEFAULT_LOAD_PROFILES.residential
      if (loadProfile && loadProfile.length > profileIndex) {
        demandKw += Number(loadProfile[profileIndex]) || 0
      } else {
        // 如果没有 loadProfile，使用 demandPower
        demandKw += Number(c.demandPower) || 0
      }
    }
  })

  return {
    maxTotalKw,
    maxActiveTotalKw,
    currentTotalKw,
    lossTotalKw,
    demandKw,
  }
})

// ==================== 动画数字 ====================
const currentKwSource = ref(0)
const lossKwSource = ref(0)

// 使用 VueUse 的 useTransition 实现数字动画
const animatedCurrentKw = useTransition(currentKwSource, {
  duration: 1500,
})
const animatedLossKw = useTransition(lossKwSource, {
  duration: 1500,
})

// 监听统计数据变化，更新动画源
watch(
  () => stats.value.currentTotalKw,
  val => {
    currentKwSource.value = val
  },
)

watch(
  () => stats.value.lossTotalKw,
  val => {
    lossKwSource.value = val
  },
)

/** 创建画布背景装饰形状 */
const createCanvasShapes = () => {
  const count = 18
  const arr = []
  for (let i = 0; i < count; i += 1) {
    arr.push({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: 120 + Math.random() * 180,
      duration: 14 + Math.random() * 10,
      delay: Math.random() * -20,
      opacity: 0.12 + Math.random() * 0.3,
      rotate: Math.random() * 360,
    })
  }
  canvasShapes.value = arr
}

// ==================== 拖拽相关函数 ====================
/**
 * 获取鼠标在画布中的位置
 * @param {MouseEvent} event 鼠标事件
 * @returns {{x: number, y: number}} 画布坐标
 */
const getCanvasPosition = event => {
  if (!canvasRef.value) return { x: 0, y: 0 }
  const rect = canvasRef.value.getBoundingClientRect()
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

/**
 * 从组件栏开始拖拽新组件
 * @param {string} type 组件类型（transformer/transformer2/user/switch）
 * @param {MouseEvent} event 鼠标事件
 */
const startDragFromPalette = (type, event) => {
  event.preventDefault()
  const pos = getCanvasPosition(event)
  const id = nextId++
  
  // 创建新组件对象
  const clone = {
    id,
    type,
    x: pos.x - 40,
    y: pos.y - 40,
    name: `${type}-${id}`,
    voltage: 0,
    current: 0,
    demandPower: type === 'user' ? 150 : 0,
    maxPowerKw: type === 'transformer' ? 200 : type === 'transformer2' ? 630 : 0,
    maxActivePowerKw: type === 'transformer' ? 160 : type === 'transformer2' ? 504 : 0,  // 最大有功功率 = 铭牌容量 × 0.8
    currentPowerKw: 0,  // 当前功率
    lossPowerKw: 0,
  }
  
  // 用户类型初始化
  if (type === 'user') {
    clone.userType = 'residential'
    clone.loadProfile = [...DEFAULT_LOAD_PROFILES.residential]
  }
  
  // 开关配置初始化
  if (type === 'switch') {
    clone.switchConfig = {}
  }
  
  clones.value.push(clone)
  dragging.value = {
    id,
    offsetX: pos.x - clone.x,
    offsetY: pos.y - clone.y,
    isNew: true,
  }
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', stopDragging)
}

/**
 * 开始拖拽已存在的组件
 * @param {Object} clone 组件对象
 * @param {MouseEvent} event 鼠标事件
 */
const startDragExisting = (clone, event) => {
  // 如果右键菜单或参数编辑器正在显示，不处理拖拽
  if (contextMenu.value.visible && contextMenu.value.cloneId === clone.id) return
  if (
    paramEditorVisible.value &&
    paramEditor.value.targetType === 'node' &&
    paramEditor.value.targetId === clone.id
  ) {
    return
  }
  event.preventDefault()
  const pos = getCanvasPosition(event)
  dragging.value = {
    id: clone.id,
    offsetX: pos.x - clone.x,
    offsetY: pos.y - clone.y,
    originalX: clone.x,
    originalY: clone.y,
  }
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', stopDragging)
}

/**
 * 处理鼠标移动
 * @param {MouseEvent} event 鼠标事件
 */
const handleMouseMove = event => {
  if (!dragging.value) return
  const pos = getCanvasPosition(event)
  const target = clones.value.find(c => c.id === dragging.value.id)
  if (!target) return
  target.x = pos.x - dragging.value.offsetX
  target.y = pos.y - dragging.value.offsetY
}

/**
 * 停止拖拽
 * @param {MouseEvent} event 鼠标事件
 */
const stopDragging = event => {
  if (dragging.value && dragging.value.isNew) {
    // 新组件拖拽结束
    const rect = canvasRef.value.getBoundingClientRect()
    // 如果鼠标位置在画布左边界左侧，取消创建
    if (event.clientX < rect.left) {
      clones.value = clones.value.filter(c => c.id !== dragging.value.id)
    } else {
      // 确认创建，发送后端请求
      const target = clones.value.find(c => c.id === dragging.value.id)
      if (target) {
        // 根据用户类型设置对应的图标
        if (target.type === 'user') {
          const userType = target.userType || 'residential'
          if (userType === 'residential') {
            target.image = jumindi_image_path
          } else if (userType === 'commercial') {
            target.image = shangchang_image_path
          } else if (userType === 'industrial') {
            target.image = huagongchang_image_path
          }
        }
        createNodeOnServer(target)
      }
    }
  } else if (dragging.value && !dragging.value.isNew) {
    // 已有组件拖拽结束，检查是否拖到组件栏（触发删除）
    const rect = canvasRef.value.getBoundingClientRect()
    if (event.clientX < rect.left) {
      const id = dragging.value.id
      const originalX = dragging.value.originalX
      const originalY = dragging.value.originalY
      const target = clones.value.find(c => c.id === id)

      // 先恢复原位
      if (target) {
        target.x = originalX
        target.y = originalY
      }

      // 弹出删除确认框
      ElMessageBox.confirm('确认要删除该组件吗？', '删除确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
        .then(() => {
          // 确认删除
          if (target && target.backendId != null) {
            deleteNodeOnServer(target.backendId)
          }
          const relatedLines = lines.value.filter(l => l.fromId === id || l.toId === id)
          relatedLines.forEach(line => {
            if (line.backendId != null) {
              deleteWireOnServer(line.backendId)
            }
          })
          clones.value = clones.value.filter(c => c.id !== id)
          lines.value = lines.value.filter(l => l.fromId !== id && l.toId !== id)
        })
        .catch(() => {
          // 取消删除，组件已在原位
        })
    }
  }
  dragging.value = null
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', stopDragging)
}

const openContextMenu = (clone, event) => {
  event.preventDefault()
  if (dragging.value) {
    dragging.value = null
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseup', stopDragging)
  }
  contextMenu.value.visible = true
  contextMenu.value.cloneId = clone.id
  
  // 创建虚拟元素用于 Popover 定位
  contextMenu.value.virtualRef = {
    getBoundingClientRect() {
      return {
        top: event.clientY,
        left: event.clientX,
        bottom: event.clientY,
        right: event.clientX,
        width: 0,
        height: 0,
      }
    },
  }
}

const closeContextMenu = () => {
  contextMenu.value.visible = false
  contextMenu.value.cloneId = null
  contextMenu.value.virtualRef = null
}

const confirmDeleteClone = () => {
  ElMessageBox.confirm('确认要删除吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      deleteClone()
    })
    .catch(() => {})
}

const confirmDeleteLine = () => {
  ElMessageBox.confirm('确认要删除连线吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      deleteLine()
    })
    .catch(() => {})
}

const deleteClone = () => {
  if (contextMenu.value.cloneId == null) return
  const id = contextMenu.value.cloneId
  const target = clones.value.find(c => c.id === id)
  if (target && target.backendId != null) {
    deleteNodeOnServer(target.backendId)
  }
  const relatedLines = lines.value.filter(l => l.fromId === id || l.toId === id)
  relatedLines.forEach(line => {
    if (line.backendId != null) {
      deleteWireOnServer(line.backendId)
    }
  })
  clones.value = clones.value.filter(c => c.id !== id)
  lines.value = lines.value.filter(l => l.fromId !== id && l.toId !== id)
  closeContextMenu()
}

const paramEditorVisible = ref(false)
let paramEditorCloseTimer = null

const closeParamEditorWithDelay = () => {
  if (paramEditorCloseTimer) {
    clearTimeout(paramEditorCloseTimer)
  }
  paramEditorCloseTimer = setTimeout(() => {
    paramEditorVisible.value = false
    paramEditor.value.virtualRef = null
    paramEditor.value.chartReady = false  // 重置图表就绪标志
    closeContextMenu()
  }, 5000)
}

const clearParamEditorCloseTimer = () => {
  if (paramEditorCloseTimer) {
    clearTimeout(paramEditorCloseTimer)
    paramEditorCloseTimer = null
  }
}

const openParamEditorForClone = event => {
  clearParamEditorCloseTimer()
  if (contextMenu.value.cloneId == null) return
  const id = contextMenu.value.cloneId
  const clone = clones.value.find(c => c.id === id)
  if (!clone) return

  const x = event?.clientX ?? 0
  const y = event?.clientY ?? 0
  paramEditor.value.virtualRef = {
    getBoundingClientRect() {
      return {
        top: y,
        left: x,
        bottom: y,
        right: x,
        width: 0,
        height: 0,
      }
    },
  }

  paramEditor.value.targetType = 'node'
  paramEditor.value.targetId = id
  paramEditor.value.nodeType = clone.type
  paramEditor.value.name = clone.name || ''

  if (clone.type === 'user') {
    paramEditor.value.demandPower = clone.demandPower
    // 读取用户类型（如果没有默认为'residential'）
    paramEditor.value.userType = clone.userType || 'residential'
    // 根据全局时间片计算对应的负荷曲线索引（0-5）
    paramEditor.value.currentTimeSlice = (simulationEngine.value.currentTimeSlice || 0) % 6
    paramEditor.value.chartReady = false  // 重置图表就绪标志
    // 加载已有的负荷曲线数据，如果没有则使用默认值
    paramEditor.value.currentLoadProfile = clone.loadProfile && clone.loadProfile.length > 0
      ? [...clone.loadProfile]
      : []
    // 初始化负荷曲线图表
    nextTick(() => {
      initUserLoadProfileChart()
    })
  } else if (clone.type === 'transformer' || clone.type === 'transformer2') {
    paramEditor.value.maxPowerKw = clone.maxPowerKw
    paramEditor.value.maxActivePowerKw = clone.maxActivePowerKw || Math.round(clone.maxPowerKw * 0.8)
    paramEditor.value.currentPowerKw = clone.currentPowerKw || 0
    paramEditor.value.lossPowerKw = clone.lossPowerKw || 0
    paramEditor.value.aiAnswer = '' // 先置空，请求后再填
    // 计算损耗
    onCurrentPowerChange()
    fetchTransformerAiResult(clone)
  } else if (clone.type === 'switch') {
    // 查找连接的变压器
    const connectedTransformers = []
    lines.value.forEach(line => {
      if (line.fromId === clone.id) {
        const node = clones.value.find(c => c.id === line.toId)
        if (node && (node.type === 'transformer' || node.type === 'transformer2')) {
          connectedTransformers.push(node)
        }
      } else if (line.toId === clone.id) {
        const node = clones.value.find(c => c.id === line.fromId)
        if (node && (node.type === 'transformer' || node.type === 'transformer2')) {
          connectedTransformers.push(node)
        }
      }
    })
    
    // 去重
    const uniqueTransformers = [...new Map(connectedTransformers.map(t => [t.id, t])).values()]

    paramEditor.value.switchLinks = uniqueTransformers.map(t => {
      const currentPower = Number(t.currentPowerKw) || 0
      const isEnabled = clone.switchConfig && clone.switchConfig[t.id]

      return {
        transformerId: t.id,
        name: t.name || `变压器-${t.id}`,
        enabled: isEnabled !== false, // 默认启用
        currentPowerKw: currentPower, // 当前输出功率
      }
    })
    paramEditor.value.aiAnswer = ''
    fetchSwitchAiResult(clone)
  } else {
    paramEditor.value.voltage = clone.voltage
    paramEditor.value.current = clone.current
  }
  
  paramEditorVisible.value = true
  closeContextMenu()
}

const startLinkFromContext = () => {
  if (contextMenu.value.cloneId == null) return
  const from = clones.value.find(c => c.id === contextMenu.value.cloneId)
  if (!from) return
  linking.value.active = true
  linking.value.fromId = from.id
  linking.value.x = from.x + 40
  linking.value.y = from.y + 40
  closeContextMenu()
  window.addEventListener('mousemove', updateLinkingPosition)
}

const updateLinkingPosition = event => {
  if (!linking.value.active) return
  const pos = getCanvasPosition(event)
  linking.value.x = pos.x
  linking.value.y = pos.y
}

const stopLinking = () => {
  linking.value.active = false
  linking.value.fromId = null
  window.removeEventListener('mousemove', updateLinkingPosition)
}

const handleCloneClick = clone => {
  if (!linking.value.active) return
  if (clone.id === linking.value.fromId) return
  const from = clones.value.find(c => c.id === linking.value.fromId)
  if (!from) {
    stopLinking()
    return
  }
  if (
    ((from.type === 'transformer' || from.type === 'transformer2') &&
      (clone.type === 'transformer' || clone.type === 'transformer2')) ||
    (from.type === 'user' && clone.type === 'user')
  ) {
    stopLinking()
    return
  }
  const fromId = linking.value.fromId
  const toId = clone.id
  const exists = lines.value.some(
    l =>
      (l.fromId === fromId && l.toId === toId) ||
      (l.fromId === toId && l.fromId === fromId),
  )
  if (exists) {
    stopLinking()
    return
  }

  // 确定线路方向：变压器 → 开关 → 用户
  let finalFromId, finalToId
  const a = from
  const b = clone

  const isTransformer = (node) => node.type === 'transformer' || node.type === 'transformer2'
  const isSwitch = (node) => node.type === 'switch'
  const isUser = (node) => node.type === 'user'

  if (isTransformer(a) && isSwitch(b)) {
    // 变压器 → 开关
    finalFromId = a.id
    finalToId = b.id
  } else if (isSwitch(a) && isTransformer(b)) {
    // 变压器 → 开关（反向连接）
    finalFromId = b.id
    finalToId = a.id
  } else if (isSwitch(a) && isUser(b)) {
    // 开关 → 用户
    finalFromId = a.id
    finalToId = b.id
  } else if (isUser(a) && isSwitch(b)) {
    // 开关 → 用户（反向连接）
    finalFromId = b.id
    finalToId = a.id
  } else if (isTransformer(a) && isUser(b)) {
    // 变压器 → 用户（直接连接）
    finalFromId = a.id
    finalToId = b.id
  } else if (isUser(a) && isTransformer(b)) {
    // 变压器 → 用户（反向直接连接）
    finalFromId = b.id
    finalToId = a.id
  } else {
    // 其他情况保持原方向
    finalFromId = fromId
    finalToId = toId
  }

  const id = nextLineId++
  const line = {
    id,
    fromId: finalFromId,
    toId: finalToId,
    name: `line-${id}`,
    power: 0,
    status: 'normal',
  }
  lines.value.push(line)

  // 更新开关配置
  const fromNode = clones.value.find(c => c.id === finalFromId)
  const toNode = clones.value.find(c => c.id === finalToId)
  if (
    fromNode && toNode &&
    isTransformer(fromNode) && isSwitch(toNode)
  ) {
    const transformer = fromNode
    const sw = toNode
    if (!sw.switchConfig) {
      sw.switchConfig = {}
    }
    if (sw.switchConfig[transformer.id] === undefined) {
      sw.switchConfig[transformer.id] = true
    }
  } else if (
    fromNode && toNode &&
    isSwitch(fromNode) && isTransformer(toNode)
  ) {
    const transformer = toNode
    const sw = fromNode
    if (!sw.switchConfig) {
      sw.switchConfig = {}
    }
    if (sw.switchConfig[transformer.id] === undefined) {
      sw.switchConfig[transformer.id] = true
    }
  }

  createWireOnServer(line)
  stopLinking()
}

// 处理画布空白区域拖动
const handleCanvasMouseDown = (event) => {
  // 只响应鼠标左键
  if (event.button !== 0) return

  // 如果 AI 调度正在运行，禁用画布拖动
  if (aiGlobal.value.running) return

  // 检查是否点击在组件上（如果点击在组件上，不处理画布拖动）
  const target = event.target
  if (target.closest('.clone')) return

  // 记录拖动起始位置
  canvasDrag.value.active = true
  canvasDrag.value.startX = event.clientX
  canvasDrag.value.startY = event.clientY

  // 记录所有组件和连线的起始位置
  canvasDrag.value.startClones = clones.value.map(c => ({ id: c.id, x: c.x, y: c.y }))
  canvasDrag.value.startLines = lines.value.map(l => ({ id: l.id, x1: l.x1, y1: l.y1, x2: l.x2, y2: l.y2 }))

  // 阻止默认事件
  event.preventDefault()

  // 添加全局事件监听
  window.addEventListener('mousemove', handleCanvasDragMove)
  window.addEventListener('mouseup', handleCanvasDragEnd)
}

const handleCanvasDragMove = (event) => {
  if (!canvasDrag.value.active) return

  // 计算偏移量
  const deltaX = event.clientX - canvasDrag.value.startX
  const deltaY = event.clientY - canvasDrag.value.startY

  // 移动所有组件
  canvasDrag.value.startClones.forEach(startClone => {
    const clone = clones.value.find(c => c.id === startClone.id)
    if (clone) {
      clone.x = startClone.x + deltaX
      clone.y = startClone.y + deltaY
    }
  })

  // 移动所有连线
  canvasDrag.value.startLines.forEach(startLine => {
    const line = lines.value.find(l => l.id === startLine.id)
    if (line) {
      line.x1 = startLine.x1 + deltaX
      line.y1 = startLine.y1 + deltaY
      line.x2 = startLine.x2 + deltaX
      line.y2 = startLine.y2 + deltaY
    }
  })
}

const handleCanvasDragEnd = () => {
  canvasDrag.value.active = false
  window.removeEventListener('mousemove', handleCanvasDragMove)
  window.removeEventListener('mouseup', handleCanvasDragEnd)
}

const handleCanvasClick = () => {
  closeContextMenu()
  closeLineMenu()
  clearParamEditorCloseTimer()
  paramEditorVisible.value = false
  paramEditor.value.virtualRef = null
  if (linking.value.active) {
    stopLinking()
  }
  // 点击空白处取消高亮
  selectedCloneId.value = null
  selectedLineId.value = null
  applyChartHighlight()
}

const openLineMenu = (line, event) => {
  event.preventDefault()
  lineMenu.value.visible = true
  lineMenu.value.lineId = line.id
  
  // 创建虚拟元素用于 Popover 定位
  lineMenu.value.virtualRef = {
    getBoundingClientRect() {
      return {
        top: event.clientY,
        left: event.clientX,
        bottom: event.clientY,
        right: event.clientX,
        width: 0,
        height: 0,
      }
    },
  }
}

const closeLineMenu = () => {
  lineMenu.value.visible = false
  lineMenu.value.lineId = null
  lineMenu.value.virtualRef = null
}

const deleteLine = () => {
  if (lineMenu.value.lineId == null) return
  const id = lineMenu.value.lineId
  const target = lines.value.find(l => l.id === id)
  if (target && target.backendId != null) {
    deleteWireOnServer(target.backendId)
  }
  lines.value = lines.value.filter(l => l.id !== id)
  closeLineMenu()
}

const getCloneCenter = id => {
  const clone = clones.value.find(c => c.id === id)
  if (!clone) return null
  return {
    x: clone.x + 40,
    y: clone.y + 40,
  }
}

const getLinePath = line => {
  const from = getCloneCenter(line.fromId)
  const to = getCloneCenter(line.toId)
  if (!from || !to) return ''
  const mx = (from.x + to.x) / 2
  const my = (from.y + to.y) / 2 - 40
  return `M ${from.x} ${from.y} Q ${mx} ${my} ${to.x} ${to.y}`
}

const getLineMidPoint = line => {
  const from = getCloneCenter(line.fromId)
  const to = getCloneCenter(line.toId)
  if (!from || !to) return { x: 0, y: 0 }
  return {
    x: (from.x + to.x) / 2,
    y: (from.y + to.y) / 2 - 8,
  }
}

const getTempLinePath = () => {
  if (!linking.value.active || linking.value.fromId == null) return ''
  const from = getCloneCenter(linking.value.fromId)
  if (!from) return ''
  const to = { x: linking.value.x, y: linking.value.y }
  const mx = (from.x + to.x) / 2
  const my = (from.y + to.y) / 2 - 40
  return `M ${from.x} ${from.y} Q ${mx} ${my} ${to.x} ${to.y}`
}

const getLineTransformerInfo = line => {
  const from = clones.value.find(c => c.id === line.fromId)
  const to = clones.value.find(c => c.id === line.toId)
  if (!from || !to) return null
  let transformerClone = null
  if (from.type === 'transformer' || from.type === 'transformer2') {
    transformerClone = from
  } else if (to.type === 'transformer' || to.type === 'transformer2') {
    transformerClone = to
  }
  if (!transformerClone || transformerClone.backendId == null) return null
  const r = aiGlobal.value.lastResult
  if (!r || !r.aiResults || !r.aiResults.transformers) return null
  const tRes = r.aiResults.transformers[transformerClone.backendId]
  if (!tRes) return null
  const rec = Number(tRes.recommendedPowerKw)
  const maxP = Number(tRes.maxPowerKw)
  const maxActiveP = Number(tRes.maxActivePowerKw) || Number(transformerClone.maxActivePowerKw) || (maxP * 0.8)
  return {
    recommended: isFinite(rec) && rec > 0 ? rec : null,
    max: isFinite(maxP) && maxP > 0 ? maxP : null,
    maxActivePower: isFinite(maxActiveP) && maxActiveP > 0 ? maxActiveP : null,
  }
}

const getLineCapacity = line => {
  const info = getLineTransformerInfo(line)
  if (!info) return 100
  if (info.recommended != null) return info.recommended
  if (info.max != null) return info.max
  return 100
}

const getLineSafetyStyle = line => {
  // 获取连接两端的类型
  const from = clones.value.find(c => c.id === line.fromId)
  const to = clones.value.find(c => c.id === line.toId)
  const power = Number(line.power) || 0

  // 1. 开关到用户：功耗越高颜色越明显（渐变青->红）
  // 简单判断：如果有一端是用户，则认为是末端线路
  if (from?.type === 'user' || to?.type === 'user') {
    // 根据用户类型获取对应的功率最大值
    const userNode = from?.type === 'user' ? from : to
    const userType = userNode?.userType || 'residential'
    const maxPower = USER_TYPE_RANGES[userType]?.max || 300
    const ratio = Math.min(power / maxPower, 1)
    // 亮青色 #22d3ee (hsl 187, 94%, 53%) -> 亮红色 #f87171 (hsl 0, 93%, 71%)
    // 增加亮度，使其在暗色背景下更醒目
    return { color: `hsl(${187 - ratio * 187}, 90%, 65%)`, dash: null }
  }

  // 2. 变压器到开关：按负载率划分（输出功率 / 有功功率）
  // 安全：< 30%，中等：30% - 60%，接近最大：60% - 90%，过载：> 90%
  const info = getLineTransformerInfo(line)
  if (!info) {
    return { color: '#22d3ee', dash: null }
  }

  // 获取有功功率
  const maxActivePower = info.maxActivePower || info.max * 0.8
  if (!maxActivePower || maxActivePower <= 0) {
    return { color: '#22d3ee', dash: null }
  }

  // 计算负载率 = 输出功率 / 有功功率
  const loadRate = power / maxActivePower

  if (loadRate <= 0.30) {
    return { color: '#4ade80', dash: null } // 安全：亮绿色
  }
  if (loadRate <= 0.60) {
    return { color: '#fbbf24', dash: null } // 中等：亮黄色
  }
  if (loadRate <= 0.90) {
    return { color: '#fb923c', dash: null } // 接近最大：亮橙色
  }
  return { color: '#f87171', dash: null }   // 过载：亮红色
}

const getLineColor = line => {
  // 如果线路被选中，返回高亮颜色
  if (selectedLineId.value !== null && selectedLineId.value === line.id) {
    return '#fbbf24' // 高亮金黄色
  }

  // 判断导线类型：从开关到用户
  const fromClone = clones.value.find(c => c.id === line.fromId)
  const toClone = clones.value.find(c => c.id === line.toId)
  const isSwitchToUser = fromClone?.type === 'switch' && toClone?.type === 'user'

  // 如果仿真结束，且功率数据可能未清零，这里需要根据 simulationRunning 决定是否显示颜色
  // 如果点击结束按钮后，line.power 仍保留值，但 simulationRunning 为 false
  // 此时应该恢复默认颜色，或者显示淡灰色（如果没有功率）

  // 修改逻辑：只有在仿真进行中，才应用功率颜色
  if (!simulationRunning.value) {
    // 恢复默认颜色，亮青色（在暗色背景下更醒目）
    return '#22d3ee'
  }

  // 如果是从开关到用户的导线，使用蓝色系
  if (isSwitchToUser) {
    const power = Number(line.power) || 0
    if (power <= 0) return '#3b82f6' // 无功率时使用较暗的蓝色
    return '#60a5fa' // 有功率时使用亮蓝色
  }

  const power = Number(line.power) || 0
  if (power <= 0) return '#94a3b8'

  if (line.status === 'warning') return '#fbbf24'
  if (line.status === 'error') return '#f87171'
  if (line.status === 'offline') return '#64748b'

  const safety = getLineSafetyStyle(line)
  // 将暗色转换为亮色
  if (safety.color === '#1e80ff' || safety.color === '#409eff' || safety.color === '#2994ff') return '#22d3ee'
  if (safety.color === '#52c41a' || safety.color === '#67c23a') return '#4ade80'
  if (safety.color === '#faad14' || safety.color === '#e6a23c') return '#fbbf24'
  if (safety.color === '#ff4d4f' || safety.color === '#f56c6c') return '#f87171'
  return safety.color
}

// 获取流动效果的高亮颜色
const getLineFlowColor = line => {
  const baseColor = getLineColor(line)
  
  // 判断是否是从开关到用户的导线
  const fromClone = clones.value.find(c => c.id === line.fromId)
  const toClone = clones.value.find(c => c.id === line.toId)
  const isSwitchToUser = fromClone?.type === 'switch' && toClone?.type === 'user'
  
  // 如果是从开关到用户的导线，使用蓝色发光效果
  if (isSwitchToUser && simulationRunning.value) {
    return '#93c5fd' // 亮蓝色发光
  }
  
  // 根据基础颜色返回更亮的高亮颜色（带发光效果）
  if (baseColor === '#22d3ee' || baseColor === '#2994ff' || baseColor === '#1e80ff' || baseColor === '#409eff') {
    return '#67e8f9' // 亮青色发光
  }
  if (baseColor === '#4ade80' || baseColor === '#52c41a' || baseColor === '#67c23a') {
    return '#86efac' // 亮绿色发光
  }
  if (baseColor === '#fbbf24' || baseColor === '#faad14' || baseColor === '#e6a23c') {
    return '#fde047' // 亮黄色发光
  }
  if (baseColor === '#f87171' || baseColor === '#ff4d4f' || baseColor === '#f56c6c') {
    return '#fca5a5' // 亮红色发光
  }
  if (baseColor === '#64748b' || baseColor === '#94a3b8' || baseColor === '#bfbfbf' || baseColor === '#d9d9d9') {
    return '#cbd5e1' // 亮灰色发光
  }
  return '#67e8f9' // 默认亮青色发光
}

/**
 * 计算导线宽度
 * 根据导线传输功率与容量的比值，动态调整导线显示宽度
 * 功率越大，导线越粗，直观反映线路负载程度
 * @param {Object} line - 导线对象
 * @returns {number} 导线宽度（2-6px）
 */
const getLineWidth = line => {
  // 如果仿真未运行，返回默认宽度
  if (!simulationRunning.value) return 2

  const power = Number(line.power) || 0
  const minW = 2   // 最小宽度
  const maxW = 6   // 最大宽度
  const capacity = getLineCapacity(line)  // 获取线路容量
  const ratio = Math.max(0, Math.min(1, power / capacity))  // 负载率（0-1）
  return minW + (maxW - minW) * ratio  // 线性插值计算宽度
}

/**
 * 计算导线不透明度
 * 根据导线传输功率与容量的比值，动态调整导线显示透明度
 * 功率越大，导线越不透明，突出高负载线路
 * @param {Object} line - 导线对象
 * @returns {number} 不透明度（0.4-1）
 */
const getLineOpacity = line => {
  // 如果仿真未运行，返回默认不透明度
  if (!simulationRunning.value) return 1

  const power = Number(line.power) || 0
  const minO = 0.4  // 最小不透明度
  const maxO = 1    // 最大不透明度
  const capacity = getLineCapacity(line)
  const ratio = Math.max(0, Math.min(1, power / capacity))
  return minO + (maxO - minO) * ratio
}

/**
 * 获取导线描边样式
 * 根据导线选中状态和功率情况，返回对应的样式对象
 * @param {Object} line - 导线对象
 * @returns {Object} 包含 strokeWidth、opacity、filter 的样式对象
 */
const getLineStrokeStyle = line => {
  // 如果导线被选中，显示高亮样式（加粗 + 发光效果）
  if (selectedLineId.value != null && line.id === selectedLineId.value) {
    return {
      strokeWidth: getLineWidth(line) + 3,
      opacity: 1,
      filter: 'drop-shadow(0 0 6px rgba(245, 158, 11, 0.75))',
    }
  }
  const power = Number(line.power) || 0
  const hasPower = power > 0
  const base = {
    strokeWidth: getLineWidth(line),
    opacity: getLineOpacity(line),
  }
  // 仿真运行时有功率的导线隐藏（由动画效果控制显示）
  if (simulationRunning.value && hasPower) {
    base.opacity = 0
  } else if (!hasPower) {
    // 无功率的导线显示为半透明
    base.opacity = 0.4
  }
  return base
}

/**
 * 获取导线箭头标记
 * 根据导线状态返回对应的箭头 SVG 标记 ID
 * @param {Object} line - 导线对象
 * @returns {string} 箭头标记 ID
 */
const getLineMarker = line => {
  if (line.status === 'warning') return 'url(#arrow-warning)'   // 警告状态（黄色箭头）
  if (line.status === 'error') return 'url(#arrow-error)'       // 错误状态（红色箭头）
  if (line.status === 'offline') return 'url(#arrow-offline)'   // 离线状态（灰色箭头）
  return 'url(#arrow-normal)'  // 正常状态（青色箭头）
}

/**
 * 获取临时颜色（预留函数）
 * @returns {string} 颜色值
 */
const getTempColor = () => '#67c23a'

/**
 * 格式化数字显示
 * 将数值格式化为保留两位小数的字符串
 * @param {number} value - 待格式化的数值
 * @returns {string} 格式化后的字符串，无效值返回 '-'
 */
const formatNumber = value => {
  const num = Number(value)
  if (!isFinite(num)) return '-'
  return num.toFixed(2)
}

/**
 * AI 调度结果摘要（计算属性）
 * 从 AI 调度结果中提取关键统计数据
 * @returns {Object|null} 包含变压器数量、开关数量、用户数量、总需求功率、总输出功率的摘要对象
 */
const aiSummary = computed(() => {
  const r = aiGlobal.value.lastResult
  if (!r) return null
  const snapshot = r.snapshot || {}
  const transformers = snapshot.transformers || {}
  const switchesSnapshot = snapshot.switches || {}
  const users = snapshot.users || {}
  
  // 计算用户总需求功率
  let totalDemandKw = 0
  Object.values(users).forEach(u => {
    const v = Number(u.demandPowerKw)
    if (isFinite(v)) totalDemandKw += v
  })
  
  // 计算变压器总输出功率
  let totalRequiredKw = 0
  const required = r.requiredPower || {}
  Object.values(required).forEach(v => {
    const n = Number(v)
    if (isFinite(n)) totalRequiredKw += n
  })
  
  return {
    transformerCount: Object.keys(transformers).length,  // 变压器数量
    switchCount: Object.keys(switchesSnapshot).length,   // 开关数量
    userCount: Object.keys(users).length,                // 用户数量
    totalDemandKw,    // 用户总需求功率 (kW)
    totalRequiredKw,  // 变压器总输出功率 (kW)
  }
})

/**
 * 构建变压器图表数据
 * 从 AI 调度结果中提取变压器的功率数据，用于 ECharts 柱状图展示
 * @returns {Object} 包含 names、current、loss、backendIds 的数据对象
 */
const buildTransformerChartData = () => {
  const r = aiGlobal.value.lastResult
  if (!r || !r.aiResults || !r.aiResults.transformers) {
    return { names: [], current: [], loss: [], backendIds: [] }
  }
  const transformers = r.aiResults.transformers
  const names = []       // 变压器名称列表
  const current = []     // 当前功率列表
  const loss = []        // 损耗功率列表
  const backendIds = []  // 后端 ID 列表（用于图表点击时定位组件）
  
  Object.keys(transformers).forEach(key => {
    const item = transformers[key] || {}
    const cur = Number(item.currentPowerKw)
    const ls = Number(item.lossPowerKw)

    // 只有当变压器当前功率大于0时，才计入图表数据
    if (cur > 0) {
      names.push(aiGetTransformerName(key))
      current.push(isFinite(cur) ? cur : 0)
      loss.push(isFinite(ls) ? ls : 0)
      backendIds.push(Number(key))
    }
  })
  return { names, current, loss, backendIds }
}

/**
 * 构建线路图表数据
 * 从当前线路列表中提取功率数据，用于 ECharts 柱状图展示
 * @returns {Object} 包含 names、power、lineIds 的数据对象
 */
const buildLineChartData = () => {
  const names = []    // 线路名称列表
  const power = []    // 功率列表
  const lineIds = []  // 线路 ID 列表（用于图表点击时定位线路）
  
  lines.value.forEach(line => {
    const name = line.name || `线路-${line.id}`
    const p = Number(line.power)
    names.push(name)
    power.push(isFinite(p) ? p : 0)
    lineIds.push(line.id)
  })
  return { names, power, lineIds }
}

/**
 * 应用图表高亮效果
 * 实现画布组件与图表的联动高亮：
 * - 当用户在画布上选中组件时，对应图表数据项高亮
 * - 当用户取消选中时，所有图表恢复正常显示
 */
const applyChartHighlight = () => {
  if (!chartVisible.value) return
  
  // 先取消所有图表的高亮状态（重置）
  if (transformerChartInstance) {
    transformerChartInstance.dispatchAction({ type: 'downplay', seriesIndex: 0 })
    transformerChartInstance.dispatchAction({ type: 'downplay', seriesIndex: 1 })
  }
  if (lineChartInstance) {
    lineChartInstance.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  }

  // 如果选中了变压器组件，在图表中高亮对应数据
  if (selectedCloneId.value != null && transformerChartInstance) {
    const clone = clones.value.find(c => c.id === selectedCloneId.value)
    const backendId = clone?.backendId
    const idx =
      backendId != null
        ? lastTransformerChartData.value.backendIds.findIndex(v => v === backendId)
        : -1
    if (idx >= 0) {
      // 高亮变压器的两个数据系列（有功功率、损耗功率）
      transformerChartInstance.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: idx })
      transformerChartInstance.dispatchAction({ type: 'highlight', seriesIndex: 1, dataIndex: idx })
    }
  }

  // 如果选中了导线，在线路图表中高亮对应数据
  if (selectedLineId.value != null && lineChartInstance) {
    const idx = lastLineChartData.value.lineIds.findIndex(v => v === selectedLineId.value)
    if (idx >= 0) {
      lineChartInstance.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: idx })
    }
  }
}

/**
 * 从图表选中变压器
 * 当用户点击变压器图表中的数据项时，选中对应的画布组件
 * @param {number} cloneId - 组件 ID
 */
const selectTransformerFromMonitor = cloneId => {
  selectedCloneId.value = cloneId
  selectedLineId.value = null
  nextTick(() => {
    applyChartHighlight()
  })
}

/**
 * 从图表选中线路
 * 当用户点击线路图表中的数据项时，选中对应的画布导线
 * @param {number} lineId - 导线 ID
 */
const selectLineFromMonitor = lineId => {
  selectedLineId.value = lineId
  selectedCloneId.value = null
  nextTick(() => {
    applyChartHighlight()
  })
}

/**
 * 更新变压器功率图表
 * 使用 ECharts 渲染变压器功率柱状图（堆叠图：有功功率 + 损耗功率）
 * 支持点击图表数据项选中对应画布组件
 */
const updateTransformerChart = () => {
  // 前置检查：图表可见性、DOM 元素存在性、尺寸有效性
  if (!chartVisible.value) return
  if (!transformerChartRef.value) return
  if (transformerChartRef.value.clientWidth === 0 || transformerChartRef.value.clientHeight === 0) return

  // 销毁旧实例，避免冲突
  if (transformerChartInstance) {
    transformerChartInstance.dispose()
    transformerChartInstance = null
  }

  // 初始化 ECharts 实例
  transformerChartInstance = echarts.init(transformerChartRef.value)
  const data = buildTransformerChartData()
  lastTransformerChartData.value = data

  // 动态计算高度：基础高度 + 每个条目 30px
  const autoHeight = Math.max(140, data.names.length * 30 + 60)
  transformerChartRef.value.style.height = `${autoHeight}px`
  transformerChartInstance.resize()

  // 图表配置项
  const option = {
    tooltip: { trigger: 'axis' },           // 鼠标悬停显示提示框
    legend: { top: 0, right: 0 },           // 图例位置
    grid: { top: 50, right: 10, bottom: 20, left: 40 },  // 图表边距
    xAxis: { type: 'category', data: data.names },       // X 轴：变压器名称
    yAxis: { type: 'value', name: 'kW' },                // Y 轴：功率值
    animation: false,                        // 禁用动画（提升性能）
    series: [
      {
        name: '有功功率',
        type: 'bar',
        stack: 'total',                      // 堆叠显示
        itemStyle: { color: '#409eff' },     // 蓝色
        emphasis: { itemStyle: { borderColor: '#111827', borderWidth: 2 } },  // 高亮样式
        data: data.current,
        animation: false,
      },
      {
        name: '损耗功率',
        type: 'bar',
        stack: 'total',
        itemStyle: { color: '#f56c6c' },     // 红色
        emphasis: { itemStyle: { borderColor: '#111827', borderWidth: 2 } },
        data: data.loss,
        animation: false,
      },
    ],
  }
  transformerChartInstance.setOption(option, true) // true 参数表示不合并旧配置

  // 绑定点击事件：点击图表数据项时选中对应画布组件
  transformerChartInstance.off('click') // 先解绑之前的
  transformerChartInstance.on('click', params => {
    if (!params || params.componentType !== 'series') return
    const backendId = lastTransformerChartData.value.backendIds[params.dataIndex]
    const target = clones.value.find(c => c.backendId === backendId)
    if (!target) return
    selectTransformerFromMonitor(target.id)
  })
  applyChartHighlight()
}

/**
 * 更新线路功耗图表
 * 使用 ECharts 渲染线路功耗柱状图
 * 支持点击图表数据项选中对应画布导线
 */
const updateLineChart = () => {
  // 前置检查
  if (!chartVisible.value) return
  if (!lineChartRef.value) return
  if (lineChartRef.value.clientWidth === 0 || lineChartRef.value.clientHeight === 0) return

  // 销毁旧实例，避免冲突
  if (lineChartInstance) {
    lineChartInstance.dispose()
    lineChartInstance = null
  }

  // 初始化 ECharts 实例
  lineChartInstance = echarts.init(lineChartRef.value)
  const data = buildLineChartData()
  lastLineChartData.value = data

  // 动态计算高度
  const autoHeight = Math.max(140, data.names.length * 30 + 60)
  lineChartRef.value.style.height = `${autoHeight}px`
  lineChartInstance.resize()

  // 图表配置项
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0 },
    grid: { left: 40, right: 16, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: data.names,
      axisLabel: { interval: 0, rotate: 30 },  // X 轴标签旋转 30 度，避免重叠
    },
    yAxis: {
      type: 'value',
      name: 'kW',
    },
    animation: false,
    series: [
      {
        name: '线路功耗',
        type: 'bar',
        itemStyle: { color: '#e6a23c' },     // 橙色
        emphasis: { itemStyle: { borderColor: '#111827', borderWidth: 2 } },
        data: data.power,
        animation: false,
      },
    ],
  }
  lineChartInstance.setOption(option, true)

  // 绑定点击事件：点击图表数据项时选中对应画布导线
  lineChartInstance.off('click')
  lineChartInstance.on('click', params => {
    if (!params || params.componentType !== 'series') return
    const lineId = lastLineChartData.value.lineIds[params.dataIndex]
    if (lineId == null) return
    selectLineFromMonitor(lineId)
  })
  applyChartHighlight()
}

// 更新总负载变化曲线图
const updateTotalLoadChart = () => {
  if (!chartVisible.value) return
  if (!totalLoadChartRef.value) return
  if (totalLoadChartRef.value.clientWidth === 0 || totalLoadChartRef.value.clientHeight === 0) return

  // 销毁旧实例
  if (totalLoadChartInstance) {
    totalLoadChartInstance.dispose()
    totalLoadChartInstance = null
  }

  totalLoadChartInstance = echarts.init(totalLoadChartRef.value)

  // 记录当前总负载
  const currentTotal = stats.value.currentTotalKw
  // 使用 TIME_LABELS 作为时间标签（与用户修改参数中的表格一致）
  const profileIndex = (simulationEngine.value.currentTimeSlice || 0) % 6
  const timeLabel = TIME_LABELS[profileIndex]

  // 添加到历史数据
  if (totalLoadHistory.value.length === 0 ||
      totalLoadHistory.value[totalLoadHistory.value.length - 1].time !== timeLabel) {
    totalLoadHistory.value.push({ time: timeLabel, value: currentTotal })
  } else {
    // 更新当前时间点的数据
    totalLoadHistory.value[totalLoadHistory.value.length - 1].value = currentTotal
  }

  const times = totalLoadHistory.value.map(d => d.time)
  const values = totalLoadHistory.value.map(d => d.value)

  // 判断是否需要显示滑动条（数据超过6个时显示）
  const showDataZoom = totalLoadHistory.value.length > 6
  // 默认显示最后6个数据
  const dataZoomEnd = showDataZoom ? (6 / totalLoadHistory.value.length) * 100 : 100

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        return `${params[0].axisValue}<br/>总负载：${params[0].value.toFixed(1)} kW`
      }
    },
    grid: { left: 50, right: 20, top: 20, bottom: showDataZoom ? 50 : 30 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { fontSize: 11, color: '#606266' },
      axisLine: { lineStyle: { color: '#dcdfe6' } }
    },
    yAxis: {
      type: 'value',
      name: 'kW',
      nameTextStyle: { fontSize: 11, color: '#909399' },
      axisLabel: { fontSize: 11, color: '#606266' },
      splitLine: { lineStyle: { color: '#f0f0f0' } }
    },
    dataZoom: showDataZoom ? [{
      type: 'slider',
      start: 100 - dataZoomEnd,
      end: 100,
      height: 18,
      bottom: 10,
      borderColor: '#dcdfe6',
      fillerColor: 'rgba(64, 158, 255, 0.2)',
      handleStyle: { color: '#409eff' },
      textStyle: { fontSize: 10, color: '#909399' },
      dataBackground: {
        lineStyle: { color: '#409eff', width: 1 },
        areaStyle: { color: 'rgba(64, 158, 255, 0.1)' }
      }
    }] : [],
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: values,
      lineStyle: { color: '#409eff', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      },
      itemStyle: { color: '#409eff' }
    }]
  }
  totalLoadChartInstance.setOption(option, true)
}

// 监听 chartVisible 变化，当变为 true 时（即图表弹窗展开），重新渲染图表
watch(chartVisible, (val) => {
  if (val) {
    // 使用 setTimeout 确保 ElPopover 内容完全渲染后再初始化图表
    setTimeout(() => {
      nextTick(() => {
        updateTotalLoadChart()
        updateTransformerChart()
        updateLineChart()
      })
    }, 50)
  }
})

onMounted(() => {
  // 初始化缩放比例
  updateUiScale()
  window.addEventListener('resize', updateUiScale)

  fetch(`${backend_base_url}/api/reset-all`, {
    method: 'POST',
  }).catch(() => {})
  createCanvasShapes()
  initParticles()
  // onMounted 时如果图表可见（虽然默认是 false），也尝试更新一下
  if (chartVisible.value && aiGlobal.value.lastResult) {
    nextTick(() => {
      updateTotalLoadChart()
      updateTransformerChart()
      updateLineChart()
    })
  }
})

watch(
  () => aiGlobal.value.lastResult,
  () => {
    nextTick(() => {
      updateTotalLoadChart()
      updateTransformerChart()
      updateLineChart()
    })
  },
)

watch(
  () => lines.value.map(l => l.power),
  () => {
    nextTick(() => {
      updateLineChart()
    })
  },
)

const aiGetTransformerName = tid => {
  const r = aiGlobal.value.lastResult
  if (!r) return `变压器`
  const snapshot = r.snapshot || {}
  const transformers = snapshot.transformers || {}
  const key = String(tid)
  const item = transformers[key]
  if (item && item.name) return item.name
  return `变压器`
}

const aiGetSwitchName = sid => {
  const r = aiGlobal.value.lastResult
  if (!r) return `开关`
  const snapshot = r.snapshot || {}
  const switchesSnapshot = snapshot.switches || {}
  const key = String(sid)
  const item = switchesSnapshot[key]
  if (item && item.name) return item.name
  return `开关`
}

const aiCountAllocations = plan => {
  if (!plan || !Array.isArray(plan.allocations)) return 0
  return plan.allocations.length
}

const aiCountUnserved = plan => {
  if (!plan) return 0
  const unserved = plan.unservedUsers
  // 仅当 unservedUsers 为数组且长度大于 0 时，才认为有未满足用户
  if (Array.isArray(unserved) && unserved.length > 0) return unserved.length
  return 0
}

const fetchTransformerAiResult = transformerClone => {
  if (!transformerClone || transformerClone.backendId == null) return
  fetch(
    `${backend_base_url}/api/blackboard/transformers/${transformerClone.backendId}`,
  )
    .then(res => {
      if (!res.ok) return null // 404 等错误直接返回 null
      return res.json()
    })
    .then(data => {
      if (!data) return
      const target = clones.value.find(c => c.id === transformerClone.id)
      if (!target) return
      if (typeof data.maxPowerKw !== 'undefined') {
        target.maxPowerKw = data.maxPowerKw
      }
      if (typeof data.maxActivePowerKw !== 'undefined') {
        target.maxActivePowerKw = data.maxActivePowerKw
      }
      if (typeof data.currentPowerKw !== 'undefined') {
        target.currentPowerKw = data.currentPowerKw
      }
      if (typeof data.lossPowerKw !== 'undefined') {
        target.lossPowerKw = data.lossPowerKw
      }
      if (
        paramEditor.value.visible &&
        paramEditor.value.targetType === 'node' &&
        (paramEditor.value.nodeType === 'transformer' ||
          paramEditor.value.nodeType === 'transformer2') &&
        paramEditor.value.targetId === transformerClone.id
      ) {
        if (typeof data.maxPowerKw !== 'undefined') {
          paramEditor.value.maxPowerKw = data.maxPowerKw
        }
        if (typeof data.maxActivePowerKw !== 'undefined') {
          paramEditor.value.maxActivePowerKw = data.maxActivePowerKw
        }
        if (typeof data.currentPowerKw !== 'undefined') {
          paramEditor.value.currentPowerKw = data.currentPowerKw
        }
        if (typeof data.lossPowerKw !== 'undefined') {
          paramEditor.value.lossPowerKw = data.lossPowerKw
        }
        if (typeof data.answer !== 'undefined') {
          paramEditor.value.aiAnswer = data.answer
        }
      }
    })
    .catch(() => {})
}

const fetchSwitchAiResult = switchClone => {
  if (!switchClone || switchClone.backendId == null) return
  fetch(`${backend_base_url}/api/blackboard/switches/${switchClone.backendId}`)
    .then(res => {
      if (!res.ok) return null
      return res.json()
    })
    .then(data => {
      if (!data) return
      if (
        paramEditor.value.visible &&
        paramEditor.value.targetType === 'node' &&
        paramEditor.value.nodeType === 'switch' &&
        paramEditor.value.targetId === switchClone.id
      ) {
        if (typeof data.answer !== 'undefined') {
          paramEditor.value.aiAnswer = data.answer
        } else if (typeof data.plan !== 'undefined') {
          try {
            paramEditor.value.aiAnswer = JSON.stringify(data.plan, null, 2)
          } catch (e) {
            paramEditor.value.aiAnswer = String(data.plan)
          }
        }
      }
    })
    .catch(() => {})
}

const createNodeOnServer = clone => {
  aiGlobal.value.needDispatch = true
  const base = {
    type: clone.type === 'transformer2' ? 'transformer' : clone.type,
    name: clone.name,
  }
  let payload
  if (clone.type === 'user') {
    payload = {
      ...base,
      demandPower: clone.demandPower,
      userType: clone.userType || 'residential',
      loadProfile: clone.loadProfile || [],
    }
  } else if (clone.type === 'transformer' || clone.type === 'transformer2') {
    payload = {
      ...base,
      maxPowerKw: clone.maxPowerKw,
      maxActivePowerKw: clone.maxActivePowerKw,
      currentPowerKw: clone.currentPowerKw,
      lossPowerKw: clone.lossPowerKw,
    }
  } else if (clone.type === 'switch') {
    payload = {
      ...base,
      config: clone.switchConfig || {},
    }
  } else {
    payload = {
      ...base,
      voltage: clone.voltage,
      current: clone.current,
    }
  }
  fetch(`${backend_base_url}/api/nodes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(res => res.json())
    .then(data => {
      if (!data || typeof data.id === 'undefined') return
      const target = clones.value.find(c => c.id === clone.id)
      if (target) {
        target.backendId = data.id
      }
    })
    .catch(() => {})
}

const createWireOnServer = line => {
  const fromClone = clones.value.find(c => c.id === line.fromId)
  const toClone = clones.value.find(c => c.id === line.toId)
  if (!fromClone || !toClone) return
  if (fromClone.backendId == null || toClone.backendId == null) return
  const payload = {
    name: line.name,
    power: line.power,
    status: line.status,
    fromComponent: fromClone.backendId,
    toComponent: toClone.backendId,
  }
  fetch(`${backend_base_url}/api/wires`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(res => res.json())
    .then(data => {
      if (!data || typeof data.id === 'undefined') return
      const target = lines.value.find(l => l.id === line.id)
      if (target) {
        target.backendId = data.id
      }
    })
    .catch(() => {})
}

const deleteNodeOnServer = backendId => {
  aiGlobal.value.needDispatch = true
  if (backendId == null) return
  fetch(`${backend_base_url}/api/nodes/${backendId}`, {
    method: 'DELETE',
  }).catch(() => {})
}

const deleteWireOnServer = backendId => {
  if (backendId == null) return
  fetch(`${backend_base_url}/api/wires/${backendId}`, {
    method: 'DELETE',
  }).catch(() => {})
}

const updateNodeOnServer = (backendId, payload) => {
  if (backendId == null) return
  fetch(`${backend_base_url}/api/nodes/${backendId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {})
}

const updateWireOnServer = (backendId, payload) => {
  if (backendId == null) return
  fetch(`${backend_base_url}/api/wires/${backendId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {})
}

const applyGlobalPlan = result => {
  if (!result || !result.aiResults) return

  try {
    const aiResults = result.aiResults
    const switchResults = aiResults.switches || {}
    const transformerResults = aiResults.transformers || {}
    const snapshot = result.snapshot || {}
    const snapshotTransformers = snapshot.transformers || {}
    const snapshotUsers = snapshot.users || {}
    const snapshotSwitches = snapshot.switches || {}
    const snapshotTransformerList = Object.keys(snapshotTransformers).map(id => ({
      id: Number(id),
      ...snapshotTransformers[id],
    }))
    const snapshotUserList = Object.keys(snapshotUsers).map(id => ({
      id: Number(id),
      ...snapshotUsers[id],
    }))
    const snapshotSwitchList = Object.keys(snapshotSwitches).map(id => ({
      id: Number(id),
      ...snapshotSwitches[id],
    }))

    clones.value.forEach(c => {
      if (c.backendId != null) return
      if (c.type === 'transformer' || c.type === 'transformer2') {
        const byName = c.name
          ? snapshotTransformerList.filter(t => t.name === c.name)
          : []
        const byPower = snapshotTransformerList.filter(t => Number(t.maxPowerKw) === Number(c.maxPowerKw))
        const candidates = byName.length > 0 ? byName : byPower
        if (candidates.length === 1 && candidates[0].id != null) {
          c.backendId = candidates[0].id
        }
        return
      }
      if (c.type === 'user') {
        const candidates = c.name
          ? snapshotUserList.filter(u => u.name === c.name)
          : []
        if (candidates.length === 1 && candidates[0].id != null) {
          c.backendId = candidates[0].id
        }
        return
      }
      if (c.type === 'switch') {
        const candidates = c.name
          ? snapshotSwitchList.filter(s => s.name === c.name)
          : []
        if (candidates.length === 1 && candidates[0].id != null) {
          c.backendId = candidates[0].id
        }
      }
    })

    const cloneByBackendId = {}
    clones.value.forEach(c => {
      if (c.backendId != null) {
        cloneByBackendId[c.backendId] = c
      }
    })

    // 更新变压器数据
    Object.keys(transformerResults).forEach(key => {
      const data = transformerResults[key]
      const backendId = Number(key)
      const tClone = cloneByBackendId[backendId]
      if (tClone) {
        if (typeof data.currentPowerKw !== 'undefined') {
          tClone.currentPowerKw = Number(data.currentPowerKw)
        }
        if (typeof data.lossPowerKw !== 'undefined') {
          tClone.lossPowerKw = Number(data.lossPowerKw)
        }
        // 如果当前参数编辑器正在显示该变压器，则实时更新
        if (
          paramEditor.value.visible &&
          paramEditor.value.targetType === 'node' &&
          (paramEditor.value.nodeType === 'transformer' ||
            paramEditor.value.nodeType === 'transformer2') &&
          paramEditor.value.targetId === tClone.id
        ) {
          if (typeof data.currentPowerKw !== 'undefined') {
            paramEditor.value.currentPowerKw = data.currentPowerKw
          }
          if (typeof data.lossPowerKw !== 'undefined') {
            paramEditor.value.lossPowerKw = data.lossPowerKw
          }
          if (typeof data.answer !== 'undefined') {
            paramEditor.value.aiAnswer = data.answer
          }
        }
      }
    })

    // 构建线路映射
    const lineByBackendPair = {}
    lines.value.forEach(line => {
      const fromClone = clones.value.find(c => c.id === line.fromId)
      const toClone = clones.value.find(c => c.id === line.toId)
      if (!fromClone || !toClone) return
      if (fromClone.backendId == null || toClone.backendId == null) return
      const key1 = `${fromClone.backendId}-${toClone.backendId}`
      const key2 = `${toClone.backendId}-${fromClone.backendId}`
      if (!lineByBackendPair[key1]) {
        lineByBackendPair[key1] = line
      }
      if (!lineByBackendPair[key2]) {
        lineByBackendPair[key2] = line
      }
    })

    lines.value.forEach(line => {
      line.power = 0
    })
    // 不要重置开关配置，保持原有状态
    // 输出为0的变压器仍然保持启用状态，以便下次调度时可以使用

    // 处理开关调度结果
    Object.keys(switchResults).forEach(key => {
      const data = switchResults[key]
      if (!data) return
      // 兼容两种数据格式：data.plan.allocations 或 data.allocations
      const plan = data.plan || data
      const allocations = Array.isArray(plan.allocations) ? plan.allocations : []
      const switchBackendId = Number(key)
      const swClone = cloneByBackendId[switchBackendId]

      if (!swClone) return

      allocations.forEach(alloc => {
        if (!alloc) return
        if (alloc.fromType !== 'transformer' || alloc.toType !== 'user') return
        let tBackendId
        let uBackendId
        let power
        try {
          tBackendId = Number(alloc.fromId)
          uBackendId = Number(alloc.toId)
          power = Number(alloc.powerKVA || alloc.powerKw)
        } catch (e) {
          return
        }
        if (!isFinite(power) || power <= 0) return
        const tClone = cloneByBackendId[tBackendId]
        const uClone = cloneByBackendId[uBackendId]
        if (!tClone || !uClone) return

        const keyTS = `${tBackendId}-${switchBackendId}`
        const keySU = `${switchBackendId}-${uBackendId}`
        const lineTS = lineByBackendPair[keyTS]
        const lineSU = lineByBackendPair[keySU]
        if (!lineTS || !lineSU) return

        lineTS.power = (Number(lineTS.power) || 0) + power
        lineSU.power = (Number(lineSU.power) || 0) + power

        if (swClone) {
          const cfg = swClone.switchConfig || {}
          cfg[tClone.id] = true
          swClone.switchConfig = cfg
          // 同步到后端
          if (swClone.backendId != null) {
            const configBackend = {}
            Object.keys(cfg).forEach(frontendId => {
              const transformer = clones.value.find(c => String(c.id) === String(frontendId))
              if (transformer && transformer.backendId != null) {
                configBackend[transformer.backendId] = cfg[frontendId]
              }
            })
            updateNodeOnServer(swClone.backendId, { config: configBackend })
          }
        }
      })
    })
    lines.value.forEach(line => {
      if (line.backendId != null) {
        updateWireOnServer(line.backendId, { power: line.power })
      }
    })
    simulationRunning.value = true
    
    // 更新总负载变化曲线
    nextTick(() => {
      updateTotalLoadChart()
    })
  } catch (e) {
    console.error('应用调度结果失败:', e)
  }
}

// 获取规划建议
const fetchPlanningSuggestions = async () => {
  // 如果已有数据，直接返回（让 Popover 显示）
  if (planningSuggestions.value.data) {
    return
  }

  planningSuggestions.value.loading = true
  planningSuggestions.value.error = ''
  // 清空已应用的建议索引
  appliedSuggestionIndices.value.clear()

  try {
    const res = await fetch(`${backend_base_url}/api/planning-suggestions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })

    if (!res.ok) {
      throw new Error('获取规划建议失败')
    }

    planningSuggestions.value.data = await res.json()
  } catch (e) {
    planningSuggestions.value.error = e.message || '获取规划建议失败'
  } finally {
    planningSuggestions.value.loading = false
  }
}

// 关闭规划建议面板
const closePlanningPopover = () => {
  if (planningPopoverRef.value) {
    planningPopoverRef.value.hide()
  }
}

// 应用规划建议
const applySuggestion = async (suggestion, index) => {
  if (applyingSuggestion.value.active) return

  applyingSuggestion.value.active = true
  applyingSuggestion.value.index = index
  applyingSuggestion.value.message = '正在应用建议...'

  try {
    const res = await fetch(`${backend_base_url}/api/apply-suggestion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actionType: suggestion.actionType,
        actionData: suggestion.actionData,
      }),
    })

    if (!res.ok) {
      throw new Error('应用建议失败')
    }

    const data = await res.json()

    if (data.success) {
      // 处理新增的变压器
      if (data.createdTransformer) {
        const t = data.createdTransformer
        // 找到目标开关的位置，在开关附近放置新变压器
        const targetSwitch = clones.value.find(c => c.backendId === suggestion.actionData.switchId)
        const newClone = {
          id: nextId++,
          type: t.type,
          x: targetSwitch ? targetSwitch.x - 200 : 300,
          y: targetSwitch ? targetSwitch.y : 300,
          name: t.name,
          voltage: 0,
          current: 0,
          demandPower: 0,
          maxPowerKw: t.maxPowerKw,
          lossPowerKw: 0,
          currentPowerKw: 0,
          backendId: t.id,
        }
        clones.value.push(newClone)
      }

      // 成功应用建议，处理创建的连线
      if (data.createdWires && data.createdWires.length > 0) {
        for (const wire of data.createdWires) {
          // 找到对应的前端组件
          let fromClone = clones.value.find(c => c.backendId === wire.fromComponent)
          let toClone = clones.value.find(c => c.backendId === wire.toComponent)

          // 如果是新增变压器的情况，fromClone 可能刚创建
          if (!fromClone && data.createdTransformer && wire.fromComponent === data.createdTransformer.id) {
            fromClone = clones.value.find(c => c.backendId === data.createdTransformer.id)
          }

          if (fromClone && toClone) {
            // 确定连线方向：变压器 → 开关 → 用户
            let finalFromId, finalToId

            const isTransformer = (node) => node.type === 'transformer' || node.type === 'transformer2'
            const isSwitch = (node) => node.type === 'switch'
            const isUser = (node) => node.type === 'user'

            if (isTransformer(fromClone) && isSwitch(toClone)) {
              finalFromId = fromClone.id
              finalToId = toClone.id
            } else if (isSwitch(fromClone) && isTransformer(toClone)) {
              finalFromId = toClone.id
              finalToId = fromClone.id
            } else if (isSwitch(fromClone) && isUser(toClone)) {
              finalFromId = fromClone.id
              finalToId = toClone.id
            } else if (isUser(fromClone) && isSwitch(toClone)) {
              finalFromId = toClone.id
              finalToId = fromClone.id
            } else if (isTransformer(fromClone) && isUser(toClone)) {
              finalFromId = fromClone.id
              finalToId = toClone.id
            } else if (isUser(fromClone) && isTransformer(toClone)) {
              finalFromId = toClone.id
              finalToId = fromClone.id
            } else {
              finalFromId = fromClone.id
              finalToId = toClone.id
            }

            const id = nextLineId++
            const newLine = {
              id,
              fromId: finalFromId,
              toId: finalToId,
              name: wire.name,
              power: 0,
              status: 'normal',
              backendId: wire.id,
            }
            lines.value.push(newLine)

            // 更新开关配置
            const fromNode = clones.value.find(c => c.id === finalFromId)
            const toNode = clones.value.find(c => c.id === finalToId)
            if (fromNode && toNode && isTransformer(fromNode) && isSwitch(toNode)) {
              if (!toNode.switchConfig) {
                toNode.switchConfig = {}
              }
              toNode.switchConfig[fromNode.id] = true
            } else if (fromNode && toNode && isSwitch(fromNode) && isTransformer(toNode)) {
              if (!fromNode.switchConfig) {
                fromNode.switchConfig = {}
              }
              fromNode.switchConfig[toNode.id] = true
            }
          }
        }
      }

      // 处理删除的连线
      if (data.deletedWires && data.deletedWires.length > 0) {
        for (const wire of data.deletedWires) {
          // 找到对应的前端连线并删除
          const lineIndex = lines.value.findIndex(l => l.backendId === wire.id)
          if (lineIndex !== -1) {
            const line = lines.value[lineIndex]
            // 更新开关配置
            const fromClone = clones.value.find(c => c.id === line.fromId)
            const toClone = clones.value.find(c => c.id === line.toId)
            if (fromClone && toClone) {
              const isTransformer = (node) => node.type === 'transformer' || node.type === 'transformer2'
              const isSwitch = (node) => node.type === 'switch'
              if (isTransformer(fromClone) && isSwitch(toClone) && toClone.switchConfig) {
                delete toClone.switchConfig[fromClone.id]
              } else if (isSwitch(fromClone) && isTransformer(toClone) && fromClone.switchConfig) {
                delete fromClone.switchConfig[toClone.id]
              }
            }
            lines.value.splice(lineIndex, 1)
          }
        }
      }

      ElMessage.success(data.message || '建议已成功应用')
      // 记录已应用的建议索引
      appliedSuggestionIndices.value.add(index)
    } else if (data.requiresManualAction) {
      // 需要手动操作
      ElMessage.info(data.message || '请手动完成此操作')
    } else {
      ElMessage.warning(data.message || '无法应用此建议')
    }

  } catch (e) {
    ElMessage.error(e.message || '应用建议失败')
  } finally {
    applyingSuggestion.value.active = false
    applyingSuggestion.value.index = null
    applyingSuggestion.value.message = ''
  }
}

// 判断建议是否可以自动应用
const canApplySuggestion = (suggestion, index) => {
  // 检查是否已应用
  if (appliedSuggestionIndices.value.has(index)) return false

  // 检查是否有有效的 actionType
  if (!suggestion.actionType) return false

  // 支持自动应用的 actionType 列表
  const applicableActionTypes = [
    'create_wire',
    'delete_wire',
    'connect_transformer_to_switch',
    'connect_user_to_switch',
    'connect_switch_to_transformer',
    'add_redundant_path',
    'add_transformer_to_switch',
  ]

  // 检查 actionType 是否在支持列表中
  if (!applicableActionTypes.includes(suggestion.actionType)) return false

  // 检查 actionData 是否有效
  const actionData = suggestion.actionData
  if (!actionData || typeof actionData !== 'object') return false

  // 根据不同的 actionType 检查必要字段
  switch (suggestion.actionType) {
    case 'create_wire':
      return actionData.fromId != null && actionData.toId != null
    case 'delete_wire':
      return actionData.wireId != null
    case 'connect_transformer_to_switch':
      return actionData.transformerId != null && actionData.switchId != null
    case 'connect_user_to_switch':
      return actionData.userId != null
    case 'connect_switch_to_transformer':
      return actionData.switchId != null
    case 'add_redundant_path':
      return actionData.userId != null
    case 'add_transformer_to_switch':
      return actionData.switchId != null
    default:
      return false
  }
}

// 获取建议优先级的颜色
const getPriorityColor = (priority) => {
  switch (priority) {
    case 'high':
      return '#f87171'
    case 'medium':
      return '#fbbf24'
    case 'low':
      return '#4ade80'
    default:
      return '#94a3b8'
  }
}

// 获取建议优先级的文字
const getPriorityText = (priority) => {
  switch (priority) {
    case 'high':
      return '高'
    case 'medium':
      return '中'
    case 'low':
      return '低'
    default:
      return '未知'
  }
}

// 获取建议类型的图标
const getSuggestionTypeIcon = (type) => {
  switch (type) {
    case 'capacity_expansion':
      return '📈'
    case 'utilization_improvement':
      return '⚡'
    case 'overload_warning':
      return '⚠️'
    case 'supply_shortage':
      return '🔌'
    case 'connectivity_issue':
      return '🔗'
    case 'line_congestion':
      return '🚧'
    case 'connection_suggestion':
      return '💡'
    case 'line_optimization':
      return '🔌'
    case 'line_removal':
      return '✂️'
    case 'redundancy_critical':
      return '🚨'
    case 'redundancy_warning':
      return '⚡'
    case 'switch_no_transformer':
      return '❌'
    case 'switch_single_transformer':
      return '🔄'
    case 'transformer_power_adjustment':
      return '⚙️'
    case 'transformer_overload':
      return '🔥'
    case 'low_utilization':
      return '📉'
    case 'load_balancing':
      return '⚖️'
    default:
      return '📋'
  }
}

const runGlobalDispatch = async (isContinue = false, isSimulation = false) => {
  // 仿真模式下使用单独的状态，非仿真模式下检查 aiGlobal.running
  if (!isSimulation && aiGlobal.value.running) return

  // 点击调度时，关闭所有右键菜单、功耗表格和弹窗
  contextMenu.value.visible = false
  lineMenu.value.visible = false
  chartVisible.value = false
  // 关闭 AI 结果弹窗
  aiGlobal.value.resultVisible = false
  // 关闭规划建议消息弹窗
  planningSuggestions.value.visible = false
  // 关闭规划建议摘要弹窗
  if (planningPopoverRef.value) {
    planningPopoverRef.value.hide()
  }

  // 非仿真模式才设置 aiGlobal.running（控制全屏遮罩）
  if (!isSimulation) {
    aiGlobal.value.running = true
    aiGlobal.value.error = ''
    aiGlobal.value.progressText = isContinue ? '正在继续调度智能体...' : '正在初始化调度...'
  } else {
    // 仿真模式设置 loading 状态（控制按钮加载动画）
    simulationEngine.value.loading = true
  }

  // 如果是继续调度，后端会处理时间片推进和用户数据更新
  // 前端只需要同步后端返回的数据

  try {
    // 1. 初始化调度 (区分是否继续)
    const initUrl = isContinue ? `${backend_base_url}/api/dispatch/continue` : `${backend_base_url}/api/dispatch/init`
    const initRes = await fetch(initUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!initRes.ok) throw new Error('初始化调度失败')
    const initData = await initRes.json()
    const switchIds = initData.switches || []

    // 同步后端返回的时间片
    if (initData.currentTimeSlice !== undefined) {
      simulationEngine.value.currentTimeSlice = initData.currentTimeSlice

      // 如果用户参数编辑器已打开，更新其中的时间片
      if (paramEditorVisible.value && paramEditor.value.nodeType === 'user') {
        setCurrentTimeSlice(initData.currentTimeSlice % 6)
      }
    }

    // 同步后端返回的用户数据（继续调度时）
    if (isContinue && initData.users) {
      Object.keys(initData.users).forEach(backendId => {
        const userData = initData.users[backendId]
        // 后端返回的键可能是字符串类型，需要比较字符串或数字
        const userClone = clones.value.find(c =>
          (c.type === 'user') &&
          (String(c.backendId) === String(backendId) || c.backendId === Number(backendId))
        )
        if (userClone && userData) {
          // 更新用户的需求功率
          if (userData.demandPowerKw !== undefined) {
            userClone.demandPower = userData.demandPowerKw
          }
          // 更新用户的负荷曲线
          if (userData.loadProfile) {
            userClone.loadProfile = userData.loadProfile
          }
        }
      })
    }

    // 2. 遍历开关进行调度
    for (let i = 0; i < switchIds.length; i++) {
      const sid = switchIds[i]
      const swClone = clones.value.find(c => c.backendId === sid)
      const swName = swClone ? swClone.name : `开关 ${sid}`
      aiGlobal.value.progressText = isContinue 
        ? `正在继续调度智能体：${swName} (${i + 1}/${switchIds.length})...`
        : `正在调度智能体：${swName} (${i + 1}/${switchIds.length})...`
      
      const swRes = await fetch(`${backend_base_url}/api/dispatch/switch/${sid}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_continue: isContinue }),
      })
      if (!swRes.ok) throw new Error(`开关 ${swName} 调度失败`)
      // 这里可以处理单个开关的返回结果，比如局部更新UI，暂且略过
    }

    // 3. 完成调度并获取最终结果
    if (!isSimulation) {
      aiGlobal.value.progressText = '正在汇总最终结果...'
    }
    const finalRes = await fetch(`${backend_base_url}/api/dispatch/finalize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!finalRes.ok) throw new Error('汇总结果失败')
    const finalData = await finalRes.json()

    // 同步后端返回的时间片
    if (finalData.currentTimeSlice !== undefined) {
      simulationEngine.value.currentTimeSlice = finalData.currentTimeSlice

      // 如果用户参数编辑器已打开，更新其中的时间片
      if (paramEditorVisible.value && paramEditor.value.nodeType === 'user') {
        setCurrentTimeSlice(finalData.currentTimeSlice % 6)
      }
    }

    aiGlobal.value.lastResult = finalData
    aiGlobal.value.needDispatch = false
    applyGlobalPlan(finalData)
    
    nextTick(() => {
      chartVisible.value = true
      simulationRunning.value = true
      // 更新总负载变化曲线
      updateTotalLoadChart()
    })

    // 延迟获取规划建�������������，避免响应式更新冲突
    setTimeout(() => {
      // 无论是否已有数据，都重新获取���划建议
      planningSuggestions.value.data = null
      fetchPlanningSuggestions()
    }, 100)

  } catch (err) {
    aiGlobal.value.error = err.message || '网络错误'
    ElMessage.error(aiGlobal.value.error)
  } finally {
    // 非仿真模式才重置 aiGlobal.running
    if (!isSimulation) {
      aiGlobal.value.running = false
      aiGlobal.value.progressText = 'AI 正在调度中，请稍候...'
    } else {
      // 仿真模式重置 loading 状态
      simulationEngine.value.loading = false
    }
  }
}

// ==================== 仿真引擎相关函数 ====================

// 打开仿真配置对话框
const openSimulationConfig = () => {
  if (simulationEngine.value.running) {
    ElMessage.warning('仿真正在运行中')
    return
  }
  simulationConfig.value.visible = true
  simulationConfig.value.delayAfterPlanning = simulationEngine.value.delayAfterPlanning / 1000
  simulationConfig.value.totalSteps = simulationEngine.value.totalSteps
}

// 关闭仿真配置对话框
const closeSimulationConfig = () => {
  simulationConfig.value.visible = false
}

// 确认仿真配置并启动
const confirmSimulationConfig = async () => {
  // 更新配置
  simulationEngine.value.delayAfterPlanning = simulationConfig.value.delayAfterPlanning * 1000
  simulationEngine.value.totalSteps = simulationConfig.value.totalSteps

  closeSimulationConfig()

  // 确认启动仿真
  try {
    await ElMessageBox.confirm(
      `仿真引擎将执行 ${simulationEngine.value.totalSteps} 个时间步长<br/>` +
      `规划后延迟：${simulationConfig.value.delayAfterPlanning} 秒<br/><br/>` +
      `仿真流程：<br/>` +
      `AI调度（初始化）→ 规划建议 → 执行建议 → 继续调度 → 规划建议（循环）`,
      '启动仿真引擎',
      {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '启动仿真',
        cancelButtonText: '取消',
        type: 'info',
      }
    )

    // 启动仿真
    startSimulation()
  } catch {
    // 用户取消
  }
}

// 启动仿真
const startSimulation = () => {
  if (simulationEngine.value.running) return

  simulationEngine.value.running = true
  simulationEngine.value.paused = false
  simulationEngine.value.status = 'running'
  simulationEngine.value.currentStep = 0
  simulationEngine.value.currentTimeSlice = 0
  simulationEngine.value.phase = 'dispatch'
  simulationEngine.value.startTime = new Date()
  simulationEngine.value.endTime = null
  
  ElMessage.success('仿真引擎已启动')
  
  // 开始执行仿真循环
  runSimulationStep()
}

// 停止仿真
const stopSimulation = async () => {
  if (!simulationEngine.value.running) return
  
  try {
    await ElMessageBox.confirm(
      '确定要停止仿真引擎吗？<br/>当前进度将丢失。',
      '停止仿真',
      {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '停止',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    simulationEngine.value.running = false
    simulationEngine.value.paused = false
    simulationEngine.value.status = 'stopped'
    simulationEngine.value.phase = 'idle'
    simulationEngine.value.endTime = new Date()
    
    ElMessage.info('仿真已停止')
  } catch {
    // 用户取消
  }
}

// 暂停/继续仿真
const toggleSimulationPause = () => {
  if (!simulationEngine.value.running) return
  
  simulationEngine.value.paused = !simulationEngine.value.paused
  
  if (simulationEngine.value.paused) {
    ElMessage.info('仿真已暂停')
  } else {
    ElMessage.success('仿真已继续')
    runSimulationStep()
  }
}

// 执行仿真步骤
const runSimulationStep = async () => {
  if (!simulationEngine.value.running || simulationEngine.value.paused) return

  // 检查是否完成所有步骤
  if (simulationEngine.value.currentStep >= simulationEngine.value.totalSteps) {
    completeSimulation()
    return
  }

  const step = simulationEngine.value.currentStep

  try {
    // 阶段 0: AI 调度（只执行一次，在第一步）
    if (simulationEngine.value.phase === 'dispatch') {
      simulationEngine.value.phase = 'dispatch'
      ElMessage.info(`初始化：AI 调度中...`)

      // 执行 AI 调度（仿真模式）
      await runGlobalDispatch(false, true)

      // 进入循环阶段
      simulationEngine.value.phase = 'planning'
      runSimulationStep()
    }
    // 阶段 1: 获取规划建议（循环起点）
    else if (simulationEngine.value.phase === 'planning') {
      simulationEngine.value.phase = 'planning'
      ElMessage.info(`第 ${step + 1}/${simulationEngine.value.totalSteps} 步：获取规划建议...`)

      // 获取规划建议
      planningSuggestions.value.data = null
      await fetchPlanningSuggestions()

      // 等待延迟时间
      await sleep(simulationEngine.value.delayAfterPlanning)

      // 进入下一阶段
      simulationEngine.value.phase = 'execute'
      runSimulationStep()
    }
    // 阶段 2: 执行规划建议
    else if (simulationEngine.value.phase === 'execute') {
      simulationEngine.value.phase = 'execute'
      ElMessage.info(`第 ${step + 1}/${simulationEngine.value.totalSteps} 步：执行规划建议...`)

      // 执行所有可自动应用的建议
      if (planningSuggestions.value.data?.suggestions?.length) {
        for (let i = 0; i < planningSuggestions.value.data.suggestions.length; i++) {
          const suggestion = planningSuggestions.value.data.suggestions[i]
          if (canApplySuggestion(suggestion, i)) {
            await applySuggestion(suggestion, i)
          }
        }
      }

      // 进入下一阶段
      simulationEngine.value.phase = 'continue'
      runSimulationStep()
    }
    // 阶段 3: 继续调度（循环回到规划建议）
    else if (simulationEngine.value.phase === 'continue') {
      simulationEngine.value.phase = 'continue'
      ElMessage.info(`第 ${step + 1}/${simulationEngine.value.totalSteps} 步：继续调度...`)

      // 执行继续调度（仿真模式）
      await runGlobalDispatch(true, true)

      // 更新步骤
      simulationEngine.value.currentStep++
      // 注意：时间片由后端推进，前端只需同步后端返回的时间片（已在 runGlobalDispatch 中处理）

      // 回到规划建议阶段（循环）
      simulationEngine.value.phase = 'planning'
      runSimulationStep()
    }
  } catch (err) {
    ElMessage.error(`仿真执行失败：${err.message}`)
    simulationEngine.value.running = false
    simulationEngine.value.status = 'error'
  }
}

// 完成仿真
const completeSimulation = () => {
  simulationEngine.value.running = false
  simulationEngine.value.status = 'completed'
  simulationEngine.value.endTime = new Date()
  simulationEngine.value.phase = 'idle'
  
  const duration = simulationEngine.value.endTime - simulationEngine.value.startTime
  ElMessage.success(`仿真完成！总耗时：${(duration / 1000).toFixed(1)} 秒`)
}

// 辅助函数：延迟
const sleep = (ms) => {
  return new Promise(resolve => setTimeout(resolve, ms))
}

const isLineCurrentActive = line => {
  if (!line) return false
  if (!simulationRunning.value) return false
  
  // 开关之间不显示流动
  const from = clones.value.find(c => c.id === line.fromId)
  const to = clones.value.find(c => c.id === line.toId)
  if (from && to && from.type === 'switch' && to.type === 'switch') {
    return false
  }

  // 检查是否有电流
  const power = Number(line.power)
  if (!isFinite(power) || power <= 0) return false
  
  const types = [from.type, to.type]
  if (
    (types.includes('transformer') || types.includes('transformer2')) &&
    types.includes('switch')
  ) {
    const transformer =
      from.type === 'transformer' || from.type === 'transformer2' ? from : to
    const sw = from.type === 'switch' ? from : to
    const config = sw.switchConfig || {}
    return config[transformer.id] === true
  }
  if (types.includes('switch') && types.includes('user')) {
    const sw = from.type === 'switch' ? from : to
    const config = sw.switchConfig || {}
    return Object.values(config).some(v => v)
  }
  return false
}

const saveWorkspace = () => {
  ElMessageBox.confirm(
    '是否保存当前工作区的内容到本地？',
    '确认保存',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    }
  )
    .then(() => {
      // 用户类型中文名称映射
      const userTypeNames = {
        residential: '居民用户',
        commercial: '商业用户',
        industrial: '工业用户',
      }

      // 为每个用户增加详细的负荷曲线信息，为变压器增加详细信息
      const enhancedClones = clones.value.map(clone => {
        if (clone.type === 'user') {
          const userType = clone.userType || 'residential'
          const loadProfile = clone.loadProfile || DEFAULT_LOAD_PROFILES[userType] || DEFAULT_LOAD_PROFILES.residential
          const range = USER_TYPE_RANGES[userType] || USER_TYPE_RANGES.residential

          return {
            ...clone,
            // 用户类型详细信息
            userTypeInfo: {
              type: userType,
              typeName: userTypeNames[userType] || '居民用户',
              powerRange: {
                min: range.min,
                max: range.max,
                default: range.default,
              },
            },
            // 负荷曲线详细信息
            loadProfileInfo: {
              timeLabels: TIME_LABELS,
              values: loadProfile,
              unit: 'kVA',
              description: `${userTypeNames[userType] || '居民用户'}的24小时负荷曲线（6个时间点采样）`,
            },
          }
        } else if (clone.type === 'transformer' || clone.type === 'transformer2') {
          // 变压器详细信息
          const maxPowerKw = clone.maxPowerKw || 0
          const maxActivePowerKw = clone.maxActivePowerKw || Math.round(maxPowerKw * 0.8)
          return {
            ...clone,
            // 变压器详细信息
            transformerInfo: {
              maxPowerKw: maxPowerKw,
              maxActivePowerKw: maxActivePowerKw,
              powerFactor: 0.8,
              description: maxPowerKw >= 400 ? 'SCB14-630kVA 二级能效变压器' : 'SCB18-200kVA 一级能效变压器',
            },
          }
        }
        return clone
      })

      const data = {
        // 元数据
        metadata: {
          exportTime: new Date().toISOString(),
          version: '1.0',
          description: '电力系统调度工作区配置文件',
        },
        // 时间标签定义
        timeLabels: TIME_LABELS,
        // 用户类型定义
        userTypes: {
          residential: {
            name: '居民用户',
            description: '早晚双高峰（18:00-20:00 最高）',
            powerRange: USER_TYPE_RANGES.residential,
            defaultProfile: DEFAULT_LOAD_PROFILES.residential,
          },
          commercial: {
            name: '商业用户',
            description: '白天营业时段高（10:00-16:00 最高）',
            powerRange: USER_TYPE_RANGES.commercial,
            defaultProfile: DEFAULT_LOAD_PROFILES.commercial,
          },
          industrial: {
            name: '工业用户',
            description: '白天持续高负荷（8:00-16:00 最高）',
            powerRange: USER_TYPE_RANGES.industrial,
            defaultProfile: DEFAULT_LOAD_PROFILES.industrial,
          },
        },
        // 组件数据
        clones: enhancedClones,
        lines: lines.value,
        nextId,
        nextLineId,
      }
      const jsonStr = JSON.stringify(data, null, 2)
      const blob = new Blob([jsonStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `workspace_backup_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      ElMessage.success('工作区保存成功')
    })
    .catch(() => {
      // 取消保存
    })
}

// 恢复工作区
const restoreWorkspace = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    try {
      const text = await file.text()
      const data = JSON.parse(text)

      if (!Array.isArray(data.clones) || !Array.isArray(data.lines)) {
        ElMessage.error('文件格式不正确')
        return
      }

      ElMessageBox.confirm(
        '恢复将覆盖当前工作区的所有内容，且无法撤销。是否继续？',
        '确认恢复',
        {
          confirmButtonText: '确定恢复',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
        .then(async () => {
          // 1. 先重置后端所有数据
          try {
            await fetch(`${backend_base_url}/api/reset-all`, {
              method: 'POST',
            })
          } catch (e) {
            // 忽略重置失败
          }

          // 2. 清空前端状态
          lines.value = []
          clones.value = []
          simulationRunning.value = false
          aiGlobal.value.lastResult = null
          aiGlobal.value.error = ''
          aiGlobal.value.resultVisible = false
          chartVisible.value = false
          contextMenu.value.visible = false

          // 3. 恢复数据
          nextId = data.nextId || 1
          nextLineId = data.nextLineId || 1
          const newClones = JSON.parse(JSON.stringify(data.clones || []))
          const newLines = JSON.parse(JSON.stringify(data.lines || []))

          // 4. 创建组件到后端并获�� backendId
          const createPromises = newClones.map(c => {
            return new Promise(resolve => {
              const base = {
                type: c.type === 'transformer2' ? 'transformer' : c.type,
                name: c.name,
              }
              let payload = base
              if (c.type === 'user') {
                // 支持新格式中的 userTypeInfo 和 loadProfileInfo
                const userType = c.userTypeInfo?.type || c.userType || 'residential'
                const loadProfile = c.loadProfileInfo?.values || c.loadProfile || DEFAULT_LOAD_PROFILES[userType] || DEFAULT_LOAD_PROFILES.residential
                payload = {
                  ...base,
                  demandPower: c.demandPower || 0,
                  userType: userType,
                  loadProfile: loadProfile,
                }
              } else if (c.type === 'transformer' || c.type === 'transformer2') {
                // 支持新格式中的 transformerInfo
                const maxPowerKw = c.transformerInfo?.maxPowerKw || c.maxPowerKw || 0
                const maxActivePowerKw = c.transformerInfo?.maxActivePowerKw || c.maxActivePowerKw || Math.round(maxPowerKw * 0.8)
                payload = {
                  ...base,
                  maxPowerKw: maxPowerKw,
                  maxActivePowerKw: maxActivePowerKw,
                  lossPowerKw: c.lossPowerKw || 0,
                  currentPowerKw: c.currentPowerKw || 0,
                }
              } else if (c.type === 'switch') {
                payload = { ...base, config: c.switchConfig || {} }
              }
              fetch(`${backend_base_url}/api/nodes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
              })
                .then(res => res.json())
                .then(resData => {
                  if (resData && typeof resData.id !== 'undefined') {
                    c.backendId = resData.id
                  }
                  resolve()
                })
                .catch(() => resolve())
            })
          })

          await Promise.all(createPromises)

          // 更新开关配置
          const switchUpdatePromises = newClones
            .filter(c => c.type === 'switch' && c.switchConfig)
            .map(c => {
              const payload = { config: c.switchConfig }
              return fetch(`${backend_base_url}/api/nodes/${c.backendId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
              })
            })

          await Promise.all(switchUpdatePromises)

          // 5. 创建连线到后端
          const createLinePromises = newLines.map(l => {
            return new Promise(resolve => {
              const fromClone = newClones.find(c => c.id === l.fromId)
              const toClone = newClones.find(c => c.id === l.toId)
              if (!fromClone || !toClone || !fromClone.backendId || !toClone.backendId) {
                resolve()
                return
              }
              const payload = {
                from: fromClone.backendId,
                to: toClone.backendId,
              }
              fetch(`${backend_base_url}/api/wires`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
              })
                .then(res => res.json())
                .then(resData => {
                  if (resData && typeof resData.id !== 'undefined') {
                    l.backendId = resData.id
                  }
                  resolve()
                })
                .catch(() => resolve())
            })
          })

          await Promise.all(createLinePromises)

          // 6. 更新前端状态
          clones.value = newClones.map(c => {
            const fromLines = newLines.filter(l => l.fromId === c.id)
            const toLines = newLines.filter(l => l.toId === c.id)
            fromLines.forEach(l => {
              l.x1 = c.x + 40
              l.y1 = c.y + 40
            })
            toLines.forEach(l => {
              l.x2 = c.x + 40
              l.y2 = c.y + 40
            })
            // 根据用户类型设置图标
            if (c.type === 'user') {
              const userType = c.userType || 'residential'
              if (userType === 'residential') {
                c.image = jumindi_image_path
              } else if (userType === 'commercial') {
                c.image = shangchang_image_path
              } else if (userType === 'industrial') {
                c.image = huagongchang_image_path
              }
            }
            return c
          })
          lines.value = newLines
          ElMessage.success('工作区恢复成功')
        })
        .catch(() => {
          // 取消恢复
        })
    } catch (e) {
      ElMessage.error('读取文件失败: ' + e.message)
    }
  }
  input.click()
}

const handleDrop = async (event) => {
  event.preventDefault()
  const files = event.dataTransfer.files
  if (files.length === 0) return

  const file = files[0]
  if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
    ElMessage.error('请拖入 JSON 格式的文件')
    return
  }

  try {
    const text = await file.text()
    const data = JSON.parse(text)

    // 简单校验数据格式
    if (!Array.isArray(data.clones) || !Array.isArray(data.lines)) {
      throw new Error('文件格式不正确')
    }

    ElMessageBox.confirm(
      '导入将覆盖当前工作区的所有内容，且无法撤销。是否继续？',
      '确认导入',
      {
        confirmButtonText: '确定覆盖',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
      .then(async () => {
        // 1. 先重置后端所有数据
        try {
          await fetch(`${backend_base_url}/api/reset-all`, {
            method: 'POST',
          })
        } catch (e) {
          // 忽略重置失败
        }

        // 2. 清空前端状态
        lines.value = []
        clones.value = []
        simulationRunning.value = false
        aiGlobal.value.lastResult = null
        aiGlobal.value.error = ''
        aiGlobal.value.resultVisible = false
        chartVisible.value = false
        contextMenu.value.visible = false
        lineMenu.value.visible = false
        clearParamEditorCloseTimer()
        paramEditorVisible.value = false
        paramEditor.value.virtualRef = null
        linking.value.active = false
        linking.value.fromId = null

        // 重置时间片为 0
        simulationEngine.value.currentTimeSlice = 0

        // 清空总负载变化曲线历史数据
        totalLoadHistory.value = []

        // 3. 重置 ID 计数器为配置文件中的最大 id + 1
        const maxCloneId = data.clones.reduce((max, c) => Math.max(max, c.id), 0)
        const maxLineId = data.lines.reduce((max, l) => Math.max(max, l.id), 0)
        nextId = maxCloneId + 1
        nextLineId = maxLineId + 1

        // 4. 创建新组件（清除旧的 backendId，保持原有 id 和名称）
        const newClones = data.clones.map(c => ({ ...c, backendId: null }))
        const newLines = data.lines.map(l => ({ ...l, backendId: null, power: 0 }))

        // 根据用户类型设置图标
        newClones.forEach(c => {
          if (c.type === 'user') {
            const userType = c.userType || 'residential'
            if (userType === 'residential') {
              c.image = jumindi_image_path
            } else if (userType === 'commercial') {
              c.image = shangchang_image_path
            } else if (userType === 'industrial') {
              c.image = huagongchang_image_path
            }
          }
        })

        clones.value = newClones
        lines.value = newLines

        // 5. 等待一小段时间确保后端重置完成
        await new Promise(resolve => setTimeout(resolve, 300))

        // 6. 同步组件到后端
        const createPromises = newClones.map(c => {
          return new Promise(resolve => {
            const base = {
              type: c.type === 'transformer2' ? 'transformer' : c.type,
              name: c.name,
            }
            let payload = base
            if (c.type === 'user') {
              // 支持新格式中的 userTypeInfo 和 loadProfileInfo
              const userType = c.userTypeInfo?.type || c.userType || 'residential'
              const loadProfile = c.loadProfileInfo?.values || c.loadProfile || DEFAULT_LOAD_PROFILES[userType] || DEFAULT_LOAD_PROFILES.residential
              payload = {
                ...base,
                demandPower: c.demandPower || 0,
                userType: userType,
                loadProfile: loadProfile,
              }
            } else if (c.type === 'transformer' || c.type === 'transformer2') {
              // 支持新格式中的 transformerInfo
              const maxPowerKw = c.transformerInfo?.maxPowerKw || c.maxPowerKw || 0
              const maxActivePowerKw = c.transformerInfo?.maxActivePowerKw || c.maxActivePowerKw || Math.round(maxPowerKw * 0.8)
              payload = {
                ...base,
                maxPowerKw: maxPowerKw,
                maxActivePowerKw: maxActivePowerKw,
                lossPowerKw: c.lossPowerKw || 0,
                currentPowerKw: c.currentPowerKw || 0,
              }
            } else if (c.type === 'switch') {
              // 先传空配置，后面等所有组件创建完成后再更新
              payload = { ...base, config: c.switchConfig || {} }
            }
            fetch(`${backend_base_url}/api/nodes`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            })
              .then(res => res.json())
              .then(resData => {
                if (resData && typeof resData.id !== 'undefined') {
                  c.backendId = resData.id
                }
                resolve()
              })
              .catch(() => resolve())
          })
        })

        // 等待所有组件创建完成
        await Promise.all(createPromises)

        // 6.1 更新开关配置（将前端 id 转换为后端 id）
        const switchUpdatePromises = newClones
          .filter(c => c.type === 'switch')
          .map(sw => {
            return new Promise(resolve => {
              const oldConfig = sw.switchConfig || {}
              const newConfig = {}
              // 将前端 id 转换为后端 id
              Object.keys(oldConfig).forEach(frontendTransformerId => {
                const transformer = newClones.find(t => String(t.id) === String(frontendTransformerId))
                if (transformer && transformer.backendId != null) {
                  newConfig[transformer.backendId] = oldConfig[frontendTransformerId]
                }
              })

              // 更新后端
              if (sw.backendId != null && Object.keys(newConfig).length > 0) {
                fetch(`${backend_base_url}/api/nodes/${sw.backendId}`, {
                  method: 'PATCH',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ config: newConfig }),
                })
                  .then(() => resolve())
                  .catch(() => resolve())
              } else {
                resolve()
              }
            })
          })

        await Promise.all(switchUpdatePromises)

        // 7. 同步线缆到后端
        const wirePromises = newLines.map(line => {
          return new Promise(resolve => {
            const fromClone = clones.value.find(c => c.id === line.fromId)
            const toClone = clones.value.find(c => c.id === line.toId)
            if (!fromClone || !toClone || fromClone.backendId == null || toClone.backendId == null) {
              resolve()
              return
            }
            const payload = {
              name: line.name,
              power: 0,
              status: line.status || 'normal',
              fromComponent: fromClone.backendId,
              toComponent: toClone.backendId,
            }
            fetch(`${backend_base_url}/api/wires`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload),
            })
              .then(res => res.json())
              .then(resData => {
                if (resData && typeof resData.id !== 'undefined') {
                  line.backendId = resData.id
                }
                resolve()
              })
              .catch(() => resolve())
          })
        })

        await Promise.all(wirePromises)

        // 8. 标记需要调度
        aiGlobal.value.needDispatch = true

        ElMessage.success('导入成功')
      })
      .catch(() => {
        ElMessage.info('已取消导入')
      })

  } catch (e) {
    ElMessage.error('读取文件失败: ' + e.message)
  }
}

const handleDragOver = (event) => {
  event.preventDefault()
}

const clearAll = () => {
  lines.value.forEach(line => {
    if (line && line.backendId != null) {
      deleteWireOnServer(line.backendId)
    }
  })
  clones.value.forEach(clone => {
    if (clone && clone.backendId != null) {
      deleteNodeOnServer(clone.backendId)
    }
  })
  lines.value = []
  clones.value = []
  linking.value.active = false
  linking.value.fromId = null
  contextMenu.value.visible = false
  lineMenu.value.visible = false
  clearParamEditorCloseTimer()
  paramEditorVisible.value = false
  paramEditor.value.virtualRef = null
  simulationRunning.value = false

  // 重置 AI 调度结果
  aiGlobal.value.lastResult = null
  aiGlobal.value.error = ''
  aiGlobal.value.resultVisible = false
  chartVisible.value = false

  // 重置时间片为 0
  simulationEngine.value.currentTimeSlice = 0

  // 清空总负载变化曲线历史数据
  totalLoadHistory.value = []
}

// 变压器损耗参数配置（与后端一致）
// 功率因数固定为 0.8
const POWER_FACTOR = 0.8

const TRANSFORMER_LOSS_CONFIGS = {
  200: {
    maxPowerKw: 200,
    noLoadLossKw: 0.32,    // 空载损耗 P₀ (kW)
    fullLoadLossKw: 1.80,  // 额定负载损耗 Pₖₙ (kW)
  },
  630: {
    maxPowerKw: 630,
    noLoadLossKw: 0.92,    // 空载损耗 P₀ (kW)
    fullLoadLossKw: 5.80,  // 额定负载损耗 Pₖₙ (kW)
  },
}

/**
 * 获取变压器损耗配置
 * @param {number} maxPowerKw - 铭牌容量 (kVA)
 * @returns {object} - 损耗配置
 */
const getTransformerLossConfig = (maxPowerKw) => {
  if (maxPowerKw >= 400) {
    return TRANSFORMER_LOSS_CONFIGS[630]
  }
  return TRANSFORMER_LOSS_CONFIGS[200]
}

/**
 * 计算变压器损耗功率
 * 公式：
 * - 视在功率 S = 当前功率 P / 功率因数 cosφ
 * - 负载率 β = S / 铭牌容量
 * - 负载损耗 Pₖ = β² × Pₖₙ
 * - 总损耗 P总 = P₀ + Pₖ
 * 
 * @param {number} maxPowerKw - 铭牌容量 (kVA)
 * @param {number} currentPowerKw - 当前功率 (kW)
 * @returns {object} - 包含 lossPowerKw, beta, noLoadLossKw, fullLoadLossKw
 */
const calculateTransformerLoss = (maxPowerKw, currentPowerKw) => {
  const config = getTransformerLossConfig(maxPowerKw)
  const p0 = config.noLoadLossKw
  const pkn = config.fullLoadLossKw

  if (!currentPowerKw || currentPowerKw <= 0) {
    return {
      lossPowerKw: 0,
      beta: 0,
      noLoadLossKw: p0,
      fullLoadLossKw: pkn,
    }
  }

  // 视在功率 S = P / cosφ
  const apparentPowerKva = currentPowerKw / POWER_FACTOR

  // 负载率 β = S / S_额定
  const beta = apparentPowerKva / maxPowerKw

  // 负载损耗 Pₖ = β² × Pₖₙ
  const loadLossKw = beta * beta * pkn

  // 总损耗 P总 = P₀ + Pₖ
  const lossPowerKw = p0 + loadLossKw

  return {
    lossPowerKw,
    beta,
    noLoadLossKw: p0,
    fullLoadLossKw: pkn,
  }
}

/**
 * 当铭牌容量变化时，更新最大有功功率
 */
const onCapacityChange = () => {
  if (paramEditor.value.nodeType !== 'transformer' && paramEditor.value.nodeType !== 'transformer2') return

  const maxPowerKw = Number(paramEditor.value.maxPowerKw) || 200
  // 最大有功功率 = 铭牌容量 × 0.8
  paramEditor.value.maxActivePowerKw = Math.round(maxPowerKw * POWER_FACTOR)

  // 如果当前功率超过最大有功功率，则限制
  if (Number(paramEditor.value.currentPowerKw) > paramEditor.value.maxActivePowerKw) {
    paramEditor.value.currentPowerKw = paramEditor.value.maxActivePowerKw
  }

  // 重新计算损耗
  onCurrentPowerChange()
}

/**
 * 当当前功率变化时，实时计算损耗
 */
const onCurrentPowerChange = () => {
  if (paramEditor.value.nodeType !== 'transformer' && paramEditor.value.nodeType !== 'transformer2') return

  const maxPowerKw = Number(paramEditor.value.maxPowerKw) || 200
  const currentPowerKw = Number(paramEditor.value.currentPowerKw) || 0

  const result = calculateTransformerLoss(maxPowerKw, currentPowerKw)
  paramEditor.value.lossPowerKw = result.lossPowerKw
}

const confirmParam = () => {
  clearParamEditorCloseTimer()
  if (!paramEditor.value.targetType || paramEditor.value.targetId == null) {
    paramEditorVisible.value = false
    return
  }
  if (paramEditor.value.targetType === 'node') {
    const target = clones.value.find(c => c.id === paramEditor.value.targetId)
    if (target) {
      target.name = paramEditor.value.name
      if (target.type === 'user') {
        target.demandPower = Number(paramEditor.value.demandPower) || 0
        target.userType = paramEditor.value.userType || 'residential'
        // 保存负荷曲线数据（6 个时间点的功率值）
        target.loadProfile = paramEditor.value.currentLoadProfile.length > 0
          ? [...paramEditor.value.currentLoadProfile]
          : [...(DEFAULT_LOAD_PROFILES[target.userType] || DEFAULT_LOAD_PROFILES.residential)]
        // 根据用户类型更新图标
        if (target.userType === 'residential') {
          target.image = jumindi_image_path
        } else if (target.userType === 'commercial') {
          target.image = shangchang_image_path
        } else if (target.userType === 'industrial') {
          target.image = huagongchang_image_path
        }
        if (target.backendId != null) {
          const payload = {
            name: target.name,
            demandPower: target.demandPower,
            userType: target.userType,
            loadProfile: target.loadProfile,
          }
          updateNodeOnServer(target.backendId, payload)
        }
      } else if (target.type === 'transformer' || target.type === 'transformer2') {
        target.maxPowerKw = Number(paramEditor.value.maxPowerKw) || 0
        target.maxActivePowerKw = Number(paramEditor.value.maxActivePowerKw) || 0
        target.currentPowerKw = Number(paramEditor.value.currentPowerKw) || 0
        target.lossPowerKw = Number(paramEditor.value.lossPowerKw) || 0
        if (target.backendId != null) {
          const payload = {
            name: target.name,
            maxPowerKw: target.maxPowerKw,
            maxActivePowerKw: target.maxActivePowerKw,
            currentPowerKw: target.currentPowerKw,
            lossPowerKw: target.lossPowerKw,
          }
          updateNodeOnServer(target.backendId, payload)
        }
      } else if (target.type === 'switch') {
        const map = {}
        const configBackend = {}
        paramEditor.value.switchLinks.forEach(item => {
          const enabled = item.enabled !== false
          map[item.transformerId] = enabled
          const transformerClone = clones.value.find(c => c.id === item.transformerId)
          if (transformerClone && transformerClone.backendId != null) {
            configBackend[transformerClone.backendId] = enabled
          }
        })
        target.switchConfig = map
        if (target.backendId != null) {
          const payload = {
            name: target.name,
            config: configBackend,
          }
          updateNodeOnServer(target.backendId, payload)
        }
      } else {
        target.voltage = Number(paramEditor.value.voltage) || 0
        target.current = Number(paramEditor.value.current) || 0
        if (target.backendId != null) {
          const payload = {
            name: target.name,
            voltage: target.voltage,
            current: target.current,
          }
          updateNodeOnServer(target.backendId, payload)
        }
      }
    }
  } else if (paramEditor.value.targetType === 'line') {
    const target = lines.value.find(l => l.id === paramEditor.value.targetId)
    if (target) {
      target.name = paramEditor.value.name
      target.power = Number(paramEditor.value.power) || 0
      target.status = paramEditor.value.status
      if (target.backendId != null) {
        const payload = {
          name: target.name,
          power: target.power,
          status: target.status,
        }
        updateWireOnServer(target.backendId, payload)
      }
    }
  }
  paramEditorVisible.value = false
  paramEditor.value.virtualRef = null
  paramEditor.value.chartReady = false  // 重置图表就绪标志
  closeContextMenu()
}

const cancelParam = () => {
  clearParamEditorCloseTimer()
  paramEditorVisible.value = false
  paramEditor.value.virtualRef = null
  paramEditor.value.chartReady = false  // 重置图表就绪标志
  closeContextMenu()
}

// ==================== 用户负荷曲线图表相关函数 ====================

// 初始化用户负荷曲线图表
const initUserLoadProfileChart = () => {
  // 使用 getElementById 获取图表容器
  const chartContainer = document.getElementById('load-profile-chart-container')
  
  if (!chartContainer) {
    setTimeout(() => {
      if (!paramEditor.value.chartReady) {
        initUserLoadProfileChart()
      }
    }, 100)
    return
  }

  // 检查容器尺寸
  const rect = chartContainer.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) {
    setTimeout(() => {
      if (!paramEditor.value.chartReady) {
        initUserLoadProfileChart()
      }
    }, 100)
    return
  }

  // 销毁旧实例
  if (loadProfileChartInstance) {
    loadProfileChartInstance.dispose()
    loadProfileChartInstance = null
  }

  const userType = paramEditor.value.userType || 'residential'
  const range = USER_TYPE_RANGES[userType]

  // 使用已有的负荷曲线数据，如果没有则使用默认值
  let powerData
  if (paramEditor.value.currentLoadProfile && paramEditor.value.currentLoadProfile.length > 0) {
    // 使用已有的数据
    powerData = paramEditor.value.currentLoadProfile.map(value => Math.max(0, Math.min(range.max, value)))
  } else {
    // 使用默认负荷曲线数据
    const defaultProfile = DEFAULT_LOAD_PROFILES[userType] || DEFAULT_LOAD_PROFILES.residential
    powerData = defaultProfile.map(value => Math.max(0, Math.min(range.max, value)))
  }

  // 设置功率为曲线最大值
  paramEditor.value.demandPower = Math.max(...powerData)
  paramEditor.value.currentLoadProfile = [...powerData]
  paramEditor.value.chartReady = true

  // 初始化图表实例
  loadProfileChartInstance = echarts.init(chartContainer)

  // Y 轴范围固定为用户类型的最大值
  const yAxisMax = range.max

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params) => {
        const dataIndex = params[0].dataIndex
        // 使用 paramEditor.value.currentLoadProfile 获取最新数据
        const currentData = paramEditor.value.currentLoadProfile
        return `${TIME_LABELS[dataIndex]}<br/>功率：${(currentData[dataIndex] || 0).toFixed(1)} kVA`
      }
    },
    grid: {
      top: 30,
      left: 50,
      right: 20,
      bottom: 30
    },
    xAxis: {
      type: 'category',
      data: TIME_LABELS,
      axisLabel: {
        color: '#606266'
      },
      axisLine: {
        lineStyle: {
          color: '#dcdfe6'
        }
      }
    },
    yAxis: {
      type: 'value',
      name: '功率 (kVA)',
      min: 0,
      max: yAxisMax,
      axisLabel: {
        color: '#606266',
        formatter: (value) => value + 'kVA'
      },
      splitLine: {
        lineStyle: {
          color: '#f0f0f0'
        }
      }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbolSize: 12,
      data: powerData.map((value, index) => ({
        value: value,
        symbol: 'circle',
        itemStyle: {
          color: index === paramEditor.value.currentTimeSlice ? '#F56C6C' : '#409EFF'
        }
      })),
      lineStyle: {
        color: '#409EFF',
        width: 2
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      }
    }]
  }

  loadProfileChartInstance.setOption(option, true)

  // 使用 graphic 组件实现可拖拽的点
  updateDraggablePoints()

  // 窗口大小调整时自适应
  window.addEventListener('resize', () => {
    if (loadProfileChartInstance) {
      loadProfileChartInstance.resize()
      updateDraggablePoints()
    }
  })
}

// 更新可拖拽的点
const updateDraggablePoints = () => {
  if (!loadProfileChartInstance || !paramEditor.value.currentLoadProfile.length) return

  const powerData = paramEditor.value.currentLoadProfile
  const symbolSize = 20
  const userType = paramEditor.value.userType || 'residential'
  const range = USER_TYPE_RANGES[userType]

  const graphics = powerData.map((value, dataIndex) => {
    const position = loadProfileChartInstance.convertToPixel('grid', [dataIndex, value])
    if (!position) return null

    // 保存原始 x 坐标，用于限制只能上下移动
    const originalX = position[0]

    return {
      type: 'circle',
      id: `drag-point-${dataIndex}`,
      x: position[0],
      y: position[1],
      shape: { r: symbolSize / 2 },
      invisible: false,
      draggable: true,
      cursor: 'ns-resize',  // 修改光标为上下调整样式
      style: {
        fill: dataIndex === paramEditor.value.currentTimeSlice ? '#F56C6C' : '#409EFF',
        opacity: 0.6
      },
      ondrag: function() {
        // 限制只能上下移动：保持 x 坐标不变，只使用 y 坐标
        const newPos = [originalX, this.y]
        const dataValue = loadProfileChartInstance.convertFromPixel('grid', newPos)
        if (!dataValue || dataValue.length < 2) return

        let newY = Math.max(0, Math.min(range.max, dataValue[1]))

        // 整刻度吸附效果：当接近整数时自动吸附
        const SNAP_THRESHOLD = 5 // 吸附阈值：距离整数 5kVA 以内时吸附
        const roundedY = Math.round(newY)
        if (Math.abs(newY - roundedY) <= SNAP_THRESHOLD) {
          newY = roundedY
        }

        // 直接更新 paramEditor 中的数据
        const currentProfile = [...paramEditor.value.currentLoadProfile]
        currentProfile[dataIndex] = newY
        paramEditor.value.currentLoadProfile = currentProfile
        paramEditor.value.demandPower = Math.round(newY)

        // 更新曲线
        loadProfileChartInstance.setOption({
          series: [{
            data: currentProfile.map((v, i) => ({
              value: v,
              symbol: 'circle',
              symbolSize: 12,
              itemStyle: {
                color: i === dataIndex ? '#F56C6C' : '#409EFF'
              }
            }))
          }]
        }, { notMerge: false })

        // 更新当前拖拽点的位置（保持 x 不变，只更新 y）
        this.attr({
          x: originalX,
          y: loadProfileChartInstance.convertToPixel('grid', [dataIndex, newY])[1]
        })
      },
      onmousemove: function() {
        showTooltip(dataIndex)
      },
      onmouseout: function() {
        hideTooltip()
      },
      z: 100
    }
  }).filter(item => item !== null)

  loadProfileChartInstance.setOption({
    graphic: graphics
  })
}

// 显示 tooltip
const showTooltip = (dataIndex) => {
  if (!loadProfileChartInstance) return
  loadProfileChartInstance.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: dataIndex
  })
}

// 隐藏 tooltip
const hideTooltip = () => {
  if (!loadProfileChartInstance) return
  loadProfileChartInstance.dispatchAction({
    type: 'hideTip'
  })
}

// 更新用户负荷曲线图表（切换用户类型时重置为默认曲线）
const updateUserLoadProfileChart = () => {
  if (!loadProfileChartInstance) return

  const userType = paramEditor.value.userType || 'residential'
  const range = USER_TYPE_RANGES[userType]

  // 重置为默认负荷曲线数据
  const defaultProfile = DEFAULT_LOAD_PROFILES[userType] || DEFAULT_LOAD_PROFILES.residential
  const powerData = defaultProfile.map(value => Math.max(0, Math.min(range.max, value)))

  // 重置默认功率为曲线最大值
  paramEditor.value.demandPower = Math.max(...powerData)
  paramEditor.value.currentLoadProfile = [...powerData]

  // Y 轴范围固定为用户类型的最大值
  const yAxisMax = range.max

  loadProfileChartInstance.setOption({
    yAxis: {
      max: yAxisMax
    },
    series: [{
      data: powerData.map((value, index) => ({
        value: value,
        symbol: 'circle',
        symbolSize: 12,
        itemStyle: {
          color: index === paramEditor.value.currentTimeSlice ? '#F56C6C' : '#409EFF'
        }
      }))
    }]
  })

  // 更新可拖拽的点
  nextTick(() => {
    updateDraggablePoints()
  })
}

// 设置当前时间片
const setCurrentTimeSlice = (slice) => {
  paramEditor.value.currentTimeSlice = slice
  if (loadProfileChartInstance && paramEditor.value.currentLoadProfile.length > 0) {
    const powerData = paramEditor.value.currentLoadProfile
    loadProfileChartInstance.setOption({
      series: [{
        data: powerData.map((value, index) => ({
          value: value,
          symbol: 'circle',
          symbolSize: 12,
          itemStyle: {
            color: index === slice ? '#F56C6C' : '#409EFF'
          }
        }))
      }]
    })
    // 更新可拖拽的点
    nextTick(() => {
      updateDraggablePoints()
    })
  }
}

// 用户类型改变时的处理
const onUserTypeChange = () => {
  updateUserLoadProfileChart()
}


onBeforeUnmount(() => {
  window.removeEventListener('resize', updateUiScale)
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', stopDragging)
  window.removeEventListener('mousemove', updateLinkingPosition)
  if (transformerChartInstance) {
    transformerChartInstance.dispose()
    transformerChartInstance = null
  }
  if (lineChartInstance) {
    lineChartInstance.dispose()
    lineChartInstance = null
  }
  if (loadProfileChartInstance) {
    loadProfileChartInstance.dispose()
    loadProfileChartInstance = null
  }
})
</script>

<template>
  <div class="main-layout">
    <aside class="palette">
      <canvas ref="paletteCanvasRef" class="palette-canvas"></canvas>
      <div class="palette-content">
        <div class="palette-header">
          <div class="palette-title">组件栏</div>
          <div class="palette-subtitle">拖动组件至演示区</div>
        </div>
      <ElDivider />
      <div class="palette-item">
        <div class="palette-label">SCB18-200kVA</div>
        <img
          class="palette-image"
          :src="transformer_image_path"
          alt="变压器"
          draggable="false"
          @mousedown="event => startDragFromPalette('transformer', event)"
        />
      </div>
      <div class="palette-item">
        <div class="palette-label">SCB14-630kVA</div>
        <img
          class="palette-image"
          :src="transformer_image_path2"
          alt="变压器2"
          draggable="false"
          @mousedown="event => startDragFromPalette('transformer2', event)"
        />
      </div>
      <div class="palette-item">
        <div class="palette-label">用户</div>
        <img
          class="palette-image"
          :src="user_image_path"
          alt="用户"
          draggable="false"
          @mousedown="event => startDragFromPalette('user', event)"
        />
      </div>
      <div class="palette-item">
        <div class="palette-label">开关</div>
        <img
          class="palette-image"
          :src="switch_image_path"
          alt="开关"
          draggable="false"
          @mousedown="event => startDragFromPalette('switch', event)"
        />
      </div>
    </div>
    </aside>
    <section class="canvas" ref="canvasRef" @mousedown="handleCanvasMouseDown" @click="handleCanvasClick" @drop="handleDrop" @dragover="handleDragOver">
      <div class="stats-overlay" :style="{ transform: `translateX(-50%) scale(${uiScale})` }">
        <ElRow :gutter="16" class="stats-row">
          <ElCol :xs="24" :sm="12" :md="6" class="stats-col">
            <ElStatistic title="总有功功率 (kW)" :value="stats.maxActiveTotalKw" :precision="2" />
          </ElCol>
          <ElCol :xs="24" :sm="12" :md="6" class="stats-col">
            <ElStatistic title="总输出功率 (kW)" :value="animatedCurrentKw" :precision="2" />
          </ElCol>
          <ElCol :xs="24" :sm="12" :md="6" class="stats-col">
            <ElStatistic title="当前总损耗 (kW)" :value="animatedLossKw" :precision="2" />
          </ElCol>
          <ElCol :xs="24" :sm="12" :md="6" class="stats-col">
            <ElStatistic title="用户总需求 (kW)" :value="stats.demandKw" :precision="2" />
          </ElCol>
        </ElRow>
      </div>
      
      <div class="canvas-bg">
        <div
          v-for="s in canvasShapes"
          :key="s.id"
          class="canvas-shape"
          :style="{
            left: `${s.x}%`,
            top: `${s.y}%`,
            '--size': `${s.size}px`,
            '--duration': `${s.duration}s`,
            '--delay': `${s.delay}s`,
            '--opacity': s.opacity,
            '--rotate': `${s.rotate}deg`,
          }"
        ></div>
      </div>
      <div class="canvas-title">工作区</div>

      <!-- 保存按钮 -->
      <div class="canvas-save-btn" :style="{ transform: `scale(${uiScale})` }" @click.stop="saveWorkspace" title="保存工作区">
        <el-icon><Download /></el-icon>
        <span class="btn-text">保存</span>
      </div>

      <!-- 恢复按钮 -->
      <div class="canvas-restore-btn" :style="{ transform: `scale(${uiScale})` }" @click.stop="restoreWorkspace" title="恢复工作区">
        <el-icon><Upload /></el-icon>
        <span class="btn-text">恢复</span>
      </div>

      <!-- 清空按钮 -->
      <div
        class="canvas-clear-btn"
        :class="{ active: clearClicked }"
        :style="{ transform: `scale(${uiScale})` }"
        title="清空画布"
        @click="confirmClearAction"
      >
        <el-icon><Delete /></el-icon>
        <span class="btn-text">清空</span>
      </div>
      <!-- 非仿真模式下显示全屏加载遮罩 -->
      <div v-if="aiGlobal.running && !simulationEngine.running" class="ai-loading-mask" v-loading="true" :element-loading-text="aiGlobal.progressText" element-loading-background="rgba(0, 0, 0, 0.5)">
      </div>

      <div class="ai-global-controls" :style="{ transform: `scale(${uiScale})` }">
        <!-- 仿真引擎控制行 -->
        <div class="ai-buttons-row simulation-control-row">
          <ElButton
            v-if="!simulationEngine.running"
            class="param-button simulation-start-btn"
            type="primary"
            :icon="Eleme"
            @click.stop="openSimulationConfig"
          >
            启动仿真
          </ElButton>
          <ElButton
            v-else
            class="param-button simulation-stop-btn"
            :class="{ 'is-loading-state': simulationEngine.loading }"
            type="danger"
            :icon="Delete"
            :loading="simulationEngine.loading"
            @click.stop="stopSimulation"
          >
            <template #loading>
              <div class="custom-loading">
                <svg class="circular" viewBox="-10, -10, 50, 50">
                  <path
                    class="path"
                    d="
                    M 30 15
                    L 28 17
                    M 25.61 25.61
                    A 15 15, 0, 0, 1, 15 30
                    A 15 15, 0, 1, 1, 27.99 7.5
                    L 15 15
                  "
                    style="stroke-width: 4px; fill: rgba(0, 0, 0, 0)"
                  />
                </svg>
              </div>
            </template>
            {{ simulationEngine.loading ? '调度中...' : '停止仿真' }}
          </ElButton>
          <ElButton
            v-if="simulationEngine.running"
            class="param-button simulation-pause-btn"
            :class="{ 'is-paused': simulationEngine.paused, 'is-running': !simulationEngine.paused }"
            :type="simulationEngine.paused ? 'success' : 'warning'"
            :icon="DataAnalysisIcon"
            @click.stop="toggleSimulationPause"
          >
            {{ simulationEngine.paused ? '继续仿真' : '暂停仿真' }}
          </ElButton>

          <!-- 仿真状态显示 -->
          <div v-if="simulationEngine.running" class="simulation-status">
            <span class="simulation-time">
              时间：{{ TIME_LABELS[simulationEngine.currentTimeSlice % 6] }}
            </span>
          </div>
        </div>
        
        <!-- 第一行：AI 调度、AI 结果、继续调度 -->
        <div class="ai-buttons-row">
          <ElButton
            class="param-button ai-dispatch-btn"
            type="success"
            :icon="DataAnalysisIcon"
            :loading="aiGlobal.running"
            @click.stop="runGlobalDispatch(false)"
          >
            <template #loading>
              <div class="custom-loading">
                <svg class="circular" viewBox="-10, -10, 50, 50">
                  <path
                    class="path"
                    d="
                    M 30 15
                    L 28 17
                    M 25.61 25.61
                    A 15 15, 0, 0, 1, 15 30
                    A 15 15, 0, 1, 1, 27.99 7.5
                    L 15 15
                  "
                    style="stroke-width: 4px; fill: rgba(0, 0, 0, 0)"
                  />
                </svg>
              </div>
            </template>
            {{ aiGlobal.running ? 'AI 调度中...' : 'AI 调度' }}
          </ElButton>

          <ElButton
            ref="aiButtonRef"
            class="param-button ai-result-btn"
            type="primary"
            v-if="aiGlobal.lastResult"
            @click.stop="toggleAiResult"
          >
            <el-icon style="margin-right: 8px;"><DataAnalysis /></el-icon>
            AI 结果
          </ElButton>

          <ElButton
            class="param-button ai-continue-btn"
            type="success"
            :icon="DataAnalysisIcon"
            v-if="aiGlobal.lastResult"
            :loading="aiGlobal.running"
            @click.stop="runGlobalDispatch(true)"
          >
            继续调度
          </ElButton>
        </div>

        <!-- 第二行：规划建议按钮和消息提示 - 在 AI 调度按钮正下方 -->
        <div class="planning-buttons-row" v-if="aiGlobal.lastResult">
          <ElPopover
            ref="planningPopoverRef"
            placement="right"
            :width="480"
            trigger="click"
            popper-class="planning-popover"
            :popper-style="'box-shadow: rgb(14 18 22 / 35%) 0px 10px 38px -10px, rgb(14 18 22 / 20%) 0px 10px 20px -15px;'"
          >
            <template #reference>
              <ElButton
                class="param-button planning-btn"
                type="warning"
                :loading="planningSuggestions.loading"
                :disabled="aiGlobal.running"
                @click.stop="!aiGlobal.running && fetchPlanningSuggestions()"
              >
                <el-icon v-if="!planningSuggestions.loading" style="margin-right: 8px;"><Sunny /></el-icon>
                {{ planningSuggestions.loading ? '分析中...' : '规划建议' }}
              </ElButton>
            </template>
            <template #default>
              <div class="planning-content">
                <div class="planning-header">
                  <span class="planning-title">电网规划建议</span>
                  <ElButton size="small" text @click="closePlanningPopover">关闭</ElButton>
                </div>

                <div v-if="planningSuggestions.loading" class="planning-loading">
                  <el-icon class="is-loading"><DataAnalysis /></el-icon>
                  <span>正在分析网络...</span>
                </div>

                <div v-else-if="planningSuggestions.error" class="planning-error">
                  {{ planningSuggestions.error }}
                </div>

                <div v-else-if="planningSuggestions.data" class="planning-body">
                  <!-- 系统状态概览 -->
                  <div class="planning-summary">
                    <div class="summary-item">
                      <span class="summary-label">系统状态</span>
                      <span class="summary-value" :class="systemHealthStatus">
                        {{ systemHealthStatus === 'good' ? '良好' :
                           systemHealthStatus === 'warning' ? '轻微' : '严重' }}
                      </span>
                    </div>
                    <div class="summary-item">
                      <span class="summary-label">建议数量</span>
                      <span class="summary-value">{{ pendingSuggestionsCount }} 条</span>
                    </div>
                    <div class="summary-item">
                      <span class="summary-label">高优先级</span>
                      <span class="summary-value high">{{ pendingHighPriorityCount }} 条</span>
                    </div>
                  </div>

                  <!-- 建议列表 -->
                  <div class="suggestions-list">
                    <div
                      v-for="item in sortedSuggestions"
                      :key="item.originalIndex"
                      class="suggestion-item"
                      :class="[item.suggestion.priority, { 'suggestion-applied-item': item.isApplied }]"
                    >
                      <div class="suggestion-header">
                        <span class="suggestion-icon">{{ getSuggestionTypeIcon(item.suggestion.type) }}</span>
                        <span class="suggestion-title">{{ item.suggestion.title }}</span>
                        <span class="suggestion-priority" :style="{ backgroundColor: getPriorityColor(item.suggestion.priority) }">
                          {{ getPriorityText(item.suggestion.priority) }}
                        </span>
                      </div>
                      <div class="suggestion-desc">{{ item.suggestion.description }}</div>
                      <div class="suggestion-recommendation">
                        <strong>建议：</strong>{{ item.suggestion.recommendation }}
                      </div>
                      <!-- 连接建议详情 -->
                      <div v-if="item.suggestion.type === 'connection_suggestion' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>变压器：{{ item.suggestion.details.transformerName }} (剩余 {{ item.suggestion.details.remainingCapacityKw?.toFixed(1) }}kW)</span>
                        </div>
                        <div class="detail-row">
                          <span>用户：{{ item.suggestion.details.userName }} (缺口 {{ item.suggestion.details.unservedKw?.toFixed(1) }}kVA)</span>
                        </div>
                        <div v-if="item.suggestion.details.bridgeSwitches?.length" class="detail-row">
                          <span>通过开关：{{ item.suggestion.details.bridgeSwitches[0].switchName }}</span>
                        </div>
                      </div>
                      <!-- 线路优化详情 -->
                      <div v-if="item.suggestion.type === 'line_optimization' && item.suggestion.details" class="suggestion-details">
                        <div v-if="item.suggestion.details.transformerName" class="detail-row">
                          <span>变压器：{{ item.suggestion.details.transformerName }}</span>
                        </div>
                        <div v-if="item.suggestion.details.switchName" class="detail-row">
                          <span>开关：{{ item.suggestion.details.switchName }}</span>
                        </div>
                        <div v-if="item.suggestion.details.userName" class="detail-row">
                          <span>用户：{{ item.suggestion.details.userName }}</span>
                        </div>
                        <div v-if="item.suggestion.details.remainingCapacityKw != null" class="detail-row">
                          <span>剩余容量：{{ item.suggestion.details.remainingCapacityKw?.toFixed(1) }}kW</span>
                        </div>
                        <div v-if="item.suggestion.details.unservedKw != null" class="detail-row">
                          <span>未满足需求：{{ item.suggestion.details.unservedKw?.toFixed(1) }}kVA</span>
                        </div>
                      </div>
                      <!-- 线路删除详情 -->
                      <div v-if="item.suggestion.type === 'line_removal' && item.suggestion.details" class="suggestion-details">
                        <div v-if="item.suggestion.details.wireId" class="detail-row">
                          <span>线路ID：{{ item.suggestion.details.wireId }}</span>
                        </div>
                        <div v-if="item.suggestion.details.wireName" class="detail-row">
                          <span>线路名称：{{ item.suggestion.details.wireName }}</span>
                        </div>
                      </div>
                      <!-- 供电不足详情 -->
                      <div v-if="item.suggestion.type === 'supply_shortage' && item.suggestion.details?.availableTransformers?.length" class="suggestion-details">
                        <div class="detail-title">可用变压器：</div>
                        <div v-for="t in item.suggestion.details.availableTransformers.slice(0, 3)" :key="t.transformerId" class="detail-row">
                          <span>{{ t.transformerName }} (剩余 {{ t.remainingCapacityKw?.toFixed(1) }}kW)</span>
                          <span v-if="t.needNewConnection" class="need-connection">需新建连接</span>
                        </div>
                      </div>
                      <!-- 网络冗余建议详情 -->
                      <div v-if="item.suggestion.type === 'redundancy_warning' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>当前路径：{{ item.suggestion.details.currentPath?.switchName }} → {{ item.suggestion.details.currentPath?.transformerName }}</span>
                        </div>
                        <div v-if="item.suggestion.details.availableBackup?.length" class="detail-title">可用备用变压器：</div>
                        <div v-for="backup in item.suggestion.details.availableBackup?.slice(0, 2)" :key="backup.transformerId" class="detail-row">
                          <span>{{ backup.transformerName }} (通过 {{ backup.switchName }}，剩余 {{ backup.remainingCapacityKw?.toFixed(1) }}kW)</span>
                        </div>
                      </div>
                      <div v-if="item.suggestion.type === 'redundancy_critical' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>用户需求：{{ item.suggestion.details.demandPowerKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div v-if="item.suggestion.details.availableBackup?.length" class="detail-title">可用变压器：</div>
                        <div v-for="backup in item.suggestion.details.availableBackup?.slice(0, 2)" :key="backup.transformerId" class="detail-row">
                          <span>{{ backup.transformerName }} (通过 {{ backup.switchName }}，剩余 {{ backup.remainingCapacityKw?.toFixed(1) }}kW)</span>
                        </div>
                      </div>
                      <div v-if="item.suggestion.type === 'switch_single_transformer' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>当前变压器：{{ item.suggestion.details.currentTransformerName }}</span>
                        </div>
                        <div v-if="item.suggestion.details.availableTransformers?.length" class="detail-title">可用备用变压器：</div>
                        <div v-for="t in item.suggestion.details.availableTransformers?.slice(0, 2)" :key="t.transformerId" class="detail-row">
                          <span>{{ t.transformerName }} (剩余 {{ t.remainingCapacityKw?.toFixed(1) }}kW)</span>
                        </div>
                      </div>
                      <!-- 变压器功率调整建议详情 -->
                      <div v-if="item.suggestion.type === 'transformer_power_adjustment' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>变压器：{{ item.suggestion.details.transformerName }}</span>
                        </div>
                        <div class="detail-row">
                          <span>当前功率：{{ item.suggestion.details.currentPowerKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div class="detail-row">
                          <span>建议功率：{{ item.suggestion.details.suggestedPowerKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div v-if="item.suggestion.details.reason" class="detail-row">
                          <span>原因：{{ item.suggestion.details.reason }}</span>
                        </div>
                      </div>
                      <!-- 变压器过载警告详情 -->
                      <div v-if="item.suggestion.type === 'transformer_overload' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>变压器：{{ item.suggestion.details.transformerName }}</span>
                        </div>
                        <div class="detail-row">
                          <span>负载率：{{ item.suggestion.details.utilizationRate?.toFixed(1) }}%</span>
                        </div>
                        <div class="detail-row">
                          <span>当前功率：{{ item.suggestion.details.currentPowerKw?.toFixed(1) }}kVA / {{ item.suggestion.details.maxPowerKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div v-if="item.suggestion.details.excessPowerKw != null" class="detail-row">
                          <span>超出容量：{{ item.suggestion.details.excessPowerKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div v-if="item.suggestion.details.targetSwitchName" class="detail-row">
                          <span>目标开关：{{ item.suggestion.details.targetSwitchName }}</span>
                        </div>
                        <div v-if="item.suggestion.details.suggestedTransformerPowerKw" class="detail-row">
                          <span>建议新增变压器容量：{{ item.suggestion.details.suggestedTransformerPowerKw?.toFixed(0) }}kVA</span>
                        </div>
                      </div>
                      <!-- 变压器利用率过低详情 -->
                      <div v-if="item.suggestion.type === 'low_utilization' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>变压器：{{ item.suggestion.details.transformerName }}</span>
                        </div>
                        <div class="detail-row">
                          <span>负载率：{{ item.suggestion.details.utilizationRate?.toFixed(1) }}%</span>
                        </div>
                        <div class="detail-row">
                          <span>当前功率：{{ item.suggestion.details.currentPowerKw?.toFixed(1) }}kVA / {{ item.suggestion.details.maxPowerKw?.toFixed(1) }}kVA</span>
                        </div>
                      </div>
                      <!-- 容量扩展建议详情 -->
                      <div v-if="item.suggestion.type === 'capacity_expansion' && item.suggestion.details" class="suggestion-details">
                        <div class="detail-row">
                          <span>总容量：{{ item.suggestion.details.totalCapacityKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div class="detail-row">
                          <span>总需求：{{ item.suggestion.details.totalDemandKw?.toFixed(1) }}kVA</span>
                        </div>
                        <div class="detail-row">
                          <span>缺口：{{ item.suggestion.details.deficitKw?.toFixed(1) }}kVA</span>
                        </div>
                      </div>
                      <!-- 负载均衡建议详情 -->
                      <div v-if="item.suggestion.type === 'load_balancing' && item.suggestion.details" class="suggestion-details">
                        <div v-if="item.suggestion.details.highLoadTransformers?.length" class="detail-title">高负载变压器：</div>
                        <div v-for="t in item.suggestion.details.highLoadTransformers?.slice(0, 2)" :key="t.id" class="detail-row">
                          <span>{{ t.name }} ({{ t.utilizationRate?.toFixed(1) }}%)</span>
                        </div>
                        <div v-if="item.suggestion.details.lowLoadTransformers?.length" class="detail-title">低负载变压器：</div>
                        <div v-for="t in item.suggestion.details.lowLoadTransformers?.slice(0, 2)" :key="t.id" class="detail-row">
                          <span>{{ t.name }} ({{ t.utilizationRate?.toFixed(1) }}%)</span>
                        </div>
                      </div>
                      <!-- 应用建议按钮 -->
                      <div v-if="canApplySuggestion(item.suggestion, item.originalIndex)" class="suggestion-action">
                        <ElButton
                          size="small"
                          type="primary"
                          :loading="applyingSuggestion.active && applyingSuggestion.index === item.originalIndex"
                          @click.stop="applySuggestion(item.suggestion, item.originalIndex)"
                        >
                          {{ applyingSuggestion.active && applyingSuggestion.index === item.originalIndex ? '应用中...' : '应用建议' }}
                        </ElButton>
                      </div>
                      <!-- 已应用标记 -->
                      <div v-if="appliedSuggestionIndices.has(item.originalIndex)" class="suggestion-applied">
                        <span>✓ 已应用</span>
                      </div>
                    </div>
                  </div>

                  <div v-if="!planningSuggestions.data.suggestions?.length" class="no-suggestions">
                    <el-icon><Eleme /></el-icon>
                    <span>当前网络状态良好，暂无优化建议</span>
                  </div>
                </div>
              </div>
            </template>
          </ElPopover>

          <!-- 黄色消息符号 - 调度完成后直接显示 -->
          <ElPopover
            v-if="planningSuggestions.data"
            placement="right"
            :width="300"
            trigger="click"
            :popper-style="'box-shadow: rgb(14 18 22 / 35%) 0px 10px 38px -10px, rgb(14 18 22 / 20%) 0px 10px 20px -15px; padding: 16px;'"
          >
            <template #reference>
              <ElBadge :value="pendingSuggestionsCount" type="warning" class="planning-badge">
                <ElButton circle size="small" type="warning">
                  <el-icon><InfoFilled /></el-icon>
                </ElButton>
              </ElBadge>
            </template>
            <template #default>
              <div class="planning-quick-summary">
                <div class="quick-summary-header">
                  <el-icon style="font-size: 20px; color: #e6a23c;"><InfoFilled /></el-icon>
                  <span style="font-weight: 600; font-size: 14px;">规划建议摘要</span>
                </div>
                <el-divider style="margin: 12px 0;" />
                <div class="quick-summary-body">
                  <div class="quick-item">
                    <span class="quick-label">系统健康度</span>
                    <span class="quick-value" :class="systemHealthStatus">
                      {{ systemHealthStatus === 'good' ? '良好' :
                         systemHealthStatus === 'warning' ? '轻微' : '严重' }}
                    </span>
                  </div>
                  <div class="quick-item">
                    <span class="quick-label">待处理建议</span>
                    <span class="quick-value">{{ pendingSuggestionsCount }} 条</span>
                  </div>
                  <div class="quick-item">
                    <span class="quick-label">高优先级</span>
                    <span class="quick-value" style="color: #f56c6c;">{{ pendingHighPriorityCount }} 条</span>
                  </div>
                  <div class="quick-item">
                    <span class="quick-label">中优先级</span>
                    <span class="quick-value" style="color: #e6a23c;">{{ pendingMediumPriorityCount }} 条</span>
                  </div>
                </div>
              </div>
            </template>
          </ElPopover>
        </div>

        <span v-if="aiGlobal.error" class="ai-global-error">{{ aiGlobal.error }}</span>
      </div>

      <ElPopover
        ref="aiResultPopoverRef"
        :virtual-ref="aiButtonRef"
        trigger="manual"
        title="AI 调度结果"
        virtual-triggering
        width="400"
        placement="bottom-start"
        :visible="aiGlobal.resultVisible"
      >
        <div class="ai-global-result-body">
          <div v-if="aiSummary" class="ai-section">
            <div class="ai-section-title">总体概览</div>
            <div class="ai-section-row">
              <span>变压器：{{ aiSummary.transformerCount }} 台</span>
              <span>开关：{{ aiSummary.switchCount }} 个</span>
              <span>用户：{{ aiSummary.userCount }} 个</span>
            </div>
            <div class="ai-section-row">
              <span>用户总需求：{{ aiSummary.totalDemandKw.toFixed(2) }} kVA</span>
              <span>变压器合计输出：{{ aiSummary.totalRequiredKw.toFixed(2) }} kVA</span>
            </div>
          </div>
          <div
            v-if="aiGlobal.lastResult && aiGlobal.lastResult.aiResults && aiGlobal.lastResult.aiResults.transformers"
            class="ai-section"
          >
            <div class="ai-section-title">变压器详情</div>
            <div
              v-for="(item, tid) in aiGlobal.lastResult.aiResults.transformers"
              :key="`tf-${tid}`"
              class="ai-item-row"
            >
              <div class="ai-item-main">
                <div class="ai-item-name">
                  {{ aiGetTransformerName(tid) }}（ID: {{ tid }}）
                </div>
                <div class="ai-item-line">
                  <span>最大功率：{{ formatNumber(item.maxPowerKw) }} kVA</span>
                  <span>当前功率：{{ formatNumber(item.currentPowerKw) }} kVA</span>
                  <span>损耗：{{ formatNumber(item.lossPowerKw) }} kVA</span>
                </div>
              </div>
            </div>
          </div>
          <div
            v-if="aiGlobal.lastResult && aiGlobal.lastResult.aiResults && aiGlobal.lastResult.aiResults.switches"
            class="ai-section"
          >
            <div class="ai-section-title">开关调度摘要</div>
            <div
              v-for="(item, sid) in aiGlobal.lastResult.aiResults.switches"
              :key="`sw-${sid}`"
              class="ai-item-row"
            >
              <div class="ai-item-main">
                <div class="ai-item-name">
                  {{ aiGetSwitchName(sid) }}（ID: {{ sid }}）
                </div>
                <div class="ai-item-line">
                  <span>分配条目：{{ aiCountAllocations(item.plan || item) }} 条</span>
                  <span>未满足用户：{{ aiCountUnserved(item.plan || item) }} 个</span>
                </div>
                <div class="ai-raw-json">{{ item.answer }}</div>
              </div>
            </div>
          </div>
        </div>
      </ElPopover>
      <svg class="connection-layer">
        <defs>
          <!-- 发光滤镜 -->
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <!-- 强发光滤镜 -->
          <filter id="glow-strong" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feGaussianBlur stdDeviation="2" result="coloredBlur2"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="coloredBlur2"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <linearGradient id="flow-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#67c23a" />
            <stop offset="50%" stop-color="#409eff" />
            <stop offset="100%" stop-color="#f56c6c" />
          </linearGradient>
          <marker id="arrow-normal" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 6 3 L 0 6 z" fill="#22d3ee" />
          </marker>
          <marker id="arrow-warning" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 6 3 L 0 6 z" fill="#fbbf24" />
          </marker>
          <marker id="arrow-error" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 6 3 L 0 6 z" fill="#f87171" />
          </marker>
          <marker id="arrow-offline" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 6 3 L 0 6 z" fill="#64748b" />
          </marker>
          <marker id="arrow-temp" viewBox="0 0 6 6" refX="6" refY="3" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 6 3 L 0 6 z" fill="#67c23a" />
          </marker>
        </defs>
        <template v-for="line in lines" :key="`line-${line.id}`">
          <!-- 背景路径 - 细线 -->
          <path
            class="connection-path-bg"
            :class="{ highlighted: selectedLineId === line.id }"
            :d="getLinePath(line)"
            :stroke="getLineColor(line)"
          />
          <!-- 前景路径 -->
          <path
            class="connection-path"
            :class="{ highlighted: selectedLineId === line.id }"
            :d="getLinePath(line)"
            :stroke="getLineColor(line)"
            :style="getLineStrokeStyle(line)"
            :marker-end="getLineMarker(line)"
          />
        </template>
        <template v-for="line in lines" :key="`flow-${line.id}`">
          <!-- 流动效果 - 外层发光 -->
          <path
            v-if="isLineCurrentActive(line)"
            class="g-rect-fill"
            :d="getLinePath(line)"
            :stroke="getLineFlowColor(line)"
            style="stroke-width: 8; opacity: 0.4;"
          />
          <!-- 流动效果 - 中层水滴 -->
          <path
            v-if="isLineCurrentActive(line)"
            class="g-rect-fill"
            :d="getLinePath(line)"
            :stroke="getLineFlowColor(line)"
          />
          <!-- 流动效果 - 内核亮点 -->
          <path
            v-if="isLineCurrentActive(line)"
            class="g-rect-fill-core"
            :d="getLinePath(line)"
            stroke="#ffffff"
          />
        </template>
        <template v-for="line in lines" :key="`label-${line.id}`">
          <text
            v-if="Number(line.power)"
            class="line-label"
            :x="getLineMidPoint(line).x"
            :y="getLineMidPoint(line).y"
          >
            {{ Number(line.power).toFixed(2) }} kW
          </text>
        </template>
        <path
          v-for="line in lines"
          :key="`hit-${line.id}`"
          class="connection-hit"
          :d="getLinePath(line)"
          @contextmenu.prevent="event => openLineMenu(line, event)"
        />
        <path
          v-if="linking.active"
          class="connection-path temp"
          :stroke="getTempColor()"
          marker-end="url(#arrow-temp)"
          :d="getTempLinePath()"
        />
      </svg>
      <ElPopover
        placement="top-start"
        :width="440"
        trigger="manual"
        :visible="chartVisible"
        popper-class="chart-popover"
        :offset="20"
      >
        <template #reference>
          <div class="chart-trigger-wrapper" :class="{ 'hidden': chartVisible }" @click="toggleChart">
            <div class="chart-trigger-btn">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="chart-trigger-icon">
                <g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
                  <circle cx="12" cy="12" r=".5" fill="currentColor"></circle>
                  <path d="M5 12a7 7 0 1 0 14 0a7 7 0 1 0-14 0m7-9v2m-9 7h2m7 7v2m7-9h2"></path>
                </g>
              </svg>
            </div>
          </div>
        </template>
        <div class="chart-content">
          <div class="chart-header-row">
            <span class="chart-main-title">实时功耗监控</span>
            <ElButton size="small" text @click="chartVisible = false">关闭</ElButton>
          </div>
          <div class="chart-scroll-container">
            <div class="chart-block">
              <div class="chart-title">总负载变化曲线</div>
              <div ref="totalLoadChartRef" class="chart-container chart-container-line"></div>
            </div>
            <div class="chart-block">
              <div class="chart-title">变压器功率与损耗</div>
              <div ref="transformerChartRef" class="chart-container"></div>
            </div>
            <div class="chart-block">
              <div class="chart-title">线路功耗</div>
              <div ref="lineChartRef" class="chart-container"></div>
            </div>
          </div>
        </div>
      </ElPopover>

      <!-- 仿真配置对话框 -->
      <ElDialog
        v-model="simulationConfig.visible"
        title="仿真引擎配置"
        width="500"
        :close-on-click-modal="false"
      >
        <div class="simulation-config-form">
          <div class="config-row">
            <span class="config-label">规划后延迟（秒）</span>
            <ElInputNumber
              v-model="simulationConfig.delayAfterPlanning"
              :min="0"
              :max="30"
              :step="0.5"
              placeholder="规划建议后等待时间"
            />
          </div>
          <div class="config-row">
            <span class="config-label">总步数</span>
            <ElInputNumber
              v-model="simulationConfig.totalSteps"
              :min="1"
              :max="99"
              :step="1"
              placeholder="仿真总步数"
            />
          </div>
          <div class="config-preview">
            <ElAlert
              title="仿真流程说明"
              type="info"
              :closable="false"
              show-icon
            >
              <template #default>
                <div class="flow-steps">
                  <div class="flow-step">
                    <ElTag size="small" type="primary">初始化</ElTag>
                    <span>AI 调度（只执行一次）</span>
                  </div>
                  <div class="flow-step">
                    <ElTag size="small" type="warning">循环</ElTag>
                    <span>规划建议 → 执行建议 → 继续调度</span>
                  </div>
                </div>
              </template>
            </ElAlert>
          </div>
        </div>
        <template #footer>
          <ElButton @click="closeSimulationConfig">取消</ElButton>
          <ElButton type="primary" @click="confirmSimulationConfig">确定</ElButton>
        </template>
      </ElDialog>

      <div class="legend-panel" @mousedown.stop>
        <div class="legend-title">线路图例</div>
        <div class="legend-row">
          <span class="legend-line legend-line-switch-user"></span>
          <span class="legend-text">开关到用户</span>
        </div>
        <div class="legend-row">
          <span class="legend-line legend-line-safe"></span>
          <span class="legend-text">安全 (&lt;30%)</span>
        </div>
        <div class="legend-row">
          <span class="legend-line legend-line-medium"></span>
          <span class="legend-text">中等 (30%-60%)</span>
        </div>
        <div class="legend-row">
          <span class="legend-line legend-line-high"></span>
          <span class="legend-text">较高 (60%-90%)</span>
        </div>
        <div class="legend-row">
          <span class="legend-line legend-line-overload"></span>
          <span class="legend-text">过载 (&gt;90%)</span>
        </div>
      </div>
      <div
        v-for="clone in clones"
        :key="clone.id"
        class="clone"
        :class="{ highlighted: selectedCloneId === clone.id }"
        :style="{
          left: `${clone.x}px`,
          top: `${clone.y}px`,
        }"
        @mousedown="event => startDragExisting(clone, event)"
        @contextmenu="event => openContextMenu(clone, event)"
        @click.stop="handleCloneClick(clone)"
      >
        <img
          class="clone-image"
          :src="
            clone.type === 'transformer'
              ? transformer_image_path
            : clone.type === 'transformer2'
                ? transformer_image_path2
                : clone.type === 'user'
                    ? (clone.image || user_image_path)
                    : switch_image_path
          "
          alt=""
          draggable="false"
        />
      </div>
      <div
        v-if="contextMenu.visible"
        class="context-menu-placeholder"
        :style="{
          position: 'fixed',
          left: '0',
          top: '0',
        }"
      ></div>
      <ElPopover
        :virtual-ref="contextMenu.virtualRef"
        trigger="manual"
        virtual-triggering
        :visible="contextMenu.visible"
        placement="right-start"
        :show-arrow="false"
        popper-class="context-menu-popover"
        @hide="closeContextMenu"
      >
        <div class="context-menu-content">
          <div class="context-menu-title">{{ contextMenuTitle }}</div>
          <ElDivider class="context-menu-divider" />
          <div class="menu-item" @click="confirmDeleteClone">删除</div>
          <ElDivider class="context-menu-divider" />
          <div class="menu-item" @click="startLinkFromContext">连线</div>
          <ElDivider class="context-menu-divider" />
          <div class="menu-item" @click="openParamEditorForClone">修改参数</div>
        </div>
      </ElPopover>

      <!-- 参数修改 Popover，移出 contextMenu 的嵌套结构 -->
      <ElPopover
        :virtual-ref="paramEditor.virtualRef"
        placement="right-start"
        :width="450"
        trigger="manual"
        virtual-triggering
        :visible="paramEditorVisible"
        @hide="closeParamEditorWithDelay"
      >
        <div class="param-editor-popover">
          <div class="param-row">
            <span class="param-label">名称</span>
            <input v-model="paramEditor.name" class="param-input param-name-input" />
          </div>
          <div
            class="param-row"
            v-if="paramEditor.targetType === 'node' && paramEditor.nodeType === 'user'"
          >
            <span class="param-label">用户类型</span>
            <ElSelect v-model="paramEditor.userType" @change="onUserTypeChange" class="param-select">
              <ElOption label="居民用户" value="residential" />
              <ElOption label="商业用户" value="commercial" />
              <ElOption label="工业用户" value="industrial" />
            </ElSelect>
          </div>
          <div
            class="param-row param-chart-row"
            v-if="paramEditor.targetType === 'node' && paramEditor.nodeType === 'user'"
          >
            <div id="load-profile-chart-container" class="load-profile-chart"></div>
            <div class="chart-time-label">当前时间片：{{ TIME_LABELS[paramEditor.currentTimeSlice] }}</div>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer'
            "
          >
            <span class="param-label">最大视在功率</span>
            <ElSlider
              v-model="paramEditor.maxPowerKw"
              :min="100"
              :max="300"
              :marks="transformerPowerMarks"
              :format-tooltip="val => val + 'kVA'"
              class="param-slider"
              @input="onCapacityChange"
            />
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer'
            "
          >
            <span class="param-label">有功功率</span>
            <span class="param-value">{{ paramEditor.maxActivePowerKw }} kW</span>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer'
            "
          >
            <span class="param-label">输出功率</span>
            <span class="param-value">{{ paramEditor.currentPowerKw?.toFixed(1) }} kW</span>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer'
            "
          >
            <span class="param-label">损耗功率</span>
            <span class="param-value">{{ paramEditor.lossPowerKw?.toFixed(3) }} kW</span>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer2'
            "
          >
            <span class="param-label">最大视在功率</span>
            <ElSlider
              v-model="paramEditor.maxPowerKw"
              :min="500"
              :max="700"
              :marks="transformer2PowerMarks"
              :format-tooltip="val => val + 'kVA'"
              class="param-slider"
              @input="onCapacityChange"
            />
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer2'
            "
          >
            <span class="param-label">有功功率</span>
            <span class="param-value">{{ paramEditor.maxActivePowerKw }} kW</span>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer2'
            "
          >
            <span class="param-label">输出功率</span>
            <span class="param-value">{{ paramEditor.currentPowerKw?.toFixed(1) }} kW</span>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              paramEditor.nodeType === 'transformer2'
            "
          >
            <span class="param-label">损耗功率</span>
            <span class="param-value">{{ paramEditor.lossPowerKw?.toFixed(3) }} kW</span>
          </div>
          <div
            class="param-row"
            v-if="
              paramEditor.targetType === 'node' &&
              (paramEditor.nodeType === 'transformer' ||
                paramEditor.nodeType === 'transformer2' ||
                paramEditor.nodeType === 'switch') &&
              paramEditor.aiAnswer
            "
          >
            <span class="param-label">AI 结果</span>
            <div class="param-ai-answer">
              {{ paramEditor.aiAnswer }}
            </div>
          </div>
          <div
            class="param-row"
            v-if="paramEditor.targetType === 'node' && paramEditor.nodeType === 'switch'"
            v-for="item in paramEditor.switchLinks"
            :key="item.transformerId"
          >
            <span class="param-label">
              {{ item.name }}
              <span v-if="item.currentPowerKw > 0" class="transformer-status active">
                ({{ item.currentPowerKw }}kVA)
              </span>
              <span v-else class="transformer-status standby">
                (待机)
              </span>
            </span>
            <ElSwitch
              v-model="item.enabled"
              size="small"
              active-text="打开"
              inactive-text="关闭"
            />
          </div>
          <div class="param-actions">
            <button class="el-button el-button--danger el-button--small" type="button" @click.stop="confirmParam">
              <span>确定</span>
            </button>
            <button class="el-button el-button--small" type="button" @click.stop="cancelParam">
              <span>取消</span>
            </button>
          </div>
        </div>
      </ElPopover>

      <div
        v-if="lineMenu.visible"
        class="context-menu-placeholder"
        :style="{
          position: 'fixed',
          left: '0',
          top: '0',
        }"
      ></div>
      <ElPopover
        :virtual-ref="lineMenu.virtualRef"
        trigger="manual"
        virtual-triggering
        :visible="lineMenu.visible"
        placement="right-start"
        :show-arrow="false"
        popper-class="context-menu-popover"
        @hide="closeLineMenu"
      >
        <div class="context-menu-content">
          <div class="context-menu-title">{{ lineMenuTitle }}</div>
          <ElDivider class="context-menu-divider" />
          <div class="menu-item" @click="confirmDeleteLine">删除连线</div>
        </div>
      </ElPopover>
    </section>
  </div>
</template>

<style scoped>
.main-layout {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
}

.canvas {
  flex: 1;
  position: relative;
  background-color: #020617;
  width: 100%;
  height: 100%;
  overflow: hidden; /* 确保 canvas 内部内容不溢出 */
}

.palette-header {
  text-align: center;
  margin-bottom: 8px;
}

.palette-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #000000;
}

.palette-subtitle {
  font-size: 12px;
  color: #888888;
}

.palette-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.2s ease;
}

.palette-item:hover {
  transform: scale(1.1);
}

.palette-label {
  margin-bottom: 8px;
  font-size: 14px;
  color: #000000;
}

.palette-image {
  width: 80px;
  height: 80px;
  object-fit: contain;
  cursor: grab;
}

.palette {
  width: 180px;
  box-sizing: border-box;
  border-right: 1px solid #e0e0e0;
  background-color: #f7f7f7;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
}

.palette::-webkit-scrollbar {
  width: 6px;
}

.palette::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.palette::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.palette::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.palette-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: auto; /* 让 canvas 接收鼠标事件 */
}

.palette-content {
  position: relative;
  z-index: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  pointer-events: none; /* 让鼠标事件穿透到 canvas */
}

.palette-item, .palette-header, .el-divider {
  pointer-events: auto; /* 恢复组件的可交互性 */
}

.stats-overlay {
  position: absolute;
  top: 16px;
  left: 50%;
  transform-origin: top center;
  z-index: 30;
  pointer-events: none;
  background-color: rgba(240, 242, 245, 0.95);
  border-radius: 8px;
  padding: 12px 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border: 1px solid #dcdfe6;
  min-width: 800px;
}

.stats-row {
  flex-wrap: nowrap;
  width: 100%;
}

.stats-col {
  min-width: 180px;
}

.canvas-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  z-index: 0;
  background: radial-gradient(circle at 10% 0%, #1e293b 0, transparent 55%),
    radial-gradient(circle at 90% 100%, #0f172a 0, transparent 55%),
    radial-gradient(circle at 50% 50%, #020617 0, #020617 70%, #000 100%);
}

.canvas-shape {
  --size: 100px;
  --opacity: 0.5;
  --duration: 10s;
  --delay: 0s;
  --rotate: 0deg;
  position: absolute;
  width: var(--size, 100px);
  height: var(--size, 100px);
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, #38bdf8, transparent 60%);
  opacity: var(--opacity, 0.5);
  filter: blur(30px);
  mix-blend-mode: screen;
  animation: canvas-shape-move var(--duration, 10s) ease-in-out infinite alternate;
  animation-delay: var(--delay, 0s);
  transform-origin: center;
}

.canvas-shape:nth-child(2n + 1) {
  background: radial-gradient(circle at 25% 25%, #6366f1, transparent 65%);
}

.canvas-shape:nth-child(3n + 1) {
  background: radial-gradient(circle at 20% 20%, #22c55e, transparent 60%);
}

@keyframes canvas-shape-move {
  0% {
    transform: translate3d(0, 0, 0) scale(1) rotate(var(--rotate, 0deg));
  }
  50% {
    transform: translate3d(24px, -28px, 0) scale(1.06) rotate(calc(var(--rotate, 0deg) + 8deg));
  }
  100% {
    transform: translate3d(-18px, 22px, 0) scale(0.97) rotate(calc(var(--rotate, 0deg) + 16deg));
  }
}

.canvas-bg,
.canvas-shape {
  pointer-events: none;
}

.canvas-save-btn {
  position: absolute;
  top: 16px;
  right: 106px; /* 清空(16) + 间距(90) */
  padding: 8px 16px;
  height: 32px;
  border-radius: 4px;
  background-color: #ffffff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  z-index: 35;
  color: #409eff; /* 默认文字颜色改为淡蓝色 (Element Plus Primary) */
  transition: all 0.3s;
  font-size: 14px;
  border: 1px solid #dcdfe6;
  gap: 6px;
  transform-origin: top right;
}

.canvas-save-btn:hover {
  background-color: #409eff;
  color: #ffffff;
  border-color: #409eff;
  box-shadow: 0 6px 20px 0 rgba(64, 158, 255, 0.5);
  top: 14px;
}

.canvas-restore-btn {
  position: absolute;
  top: 16px;
  right: 196px; /* 保存(106) + 间距(90) */
  padding: 8px 16px;
  height: 32px;
  border-radius: 4px;
  background-color: #ffffff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  z-index: 35;
  color: #67c23a;
  transition: all 0.3s;
  font-size: 14px;
  border: 1px solid #dcdfe6;
  gap: 6px;
  transform-origin: top right;
}

.canvas-restore-btn:hover {
  background-color: #67c23a;
  color: #ffffff;
  border-color: #67c23a;
  box-shadow: 0 6px 20px 0 rgba(103, 194, 58, 0.5);
  top: 14px;
}

.canvas-clear-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 8px 16px;
  height: 32px;
  border-radius: 4px;
  background-color: #ffffff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  z-index: 35;
  color: #f56c6c; /* 默认文字颜色改为淡红色 (Element Plus Danger) */
  transition: all 0.3s;
  font-size: 14px;
  border: 1px solid #dcdfe6;
  gap: 6px;
  transform-origin: top right;
}

.canvas-clear-btn:hover,
.canvas-clear-btn.active {
  background-color: #f56c6c;
  color: #ffffff;
  border-color: #f56c6c;
  box-shadow: 0 6px 20px 0 rgba(245, 108, 108, 0.5);
  top: 14px;
}

.canvas-title {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 32px;
  color: #e0e0e0;
  pointer-events: none;
  user-select: none;
}

.connection-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: auto;
  z-index: 1;
}

.connection-path {
  fill: none;
  stroke: #2994ff;
  stroke-width: 2;
}

.connection-path.temp {
  stroke-dasharray: 4 4;
}

.connection-path-bg {
  fill: none;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
  opacity: 0.25;
}

.connection-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 16;
  pointer-events: stroke;
}

/* 流动效果前景路径 - 水滴状电流 */
.g-rect-fill {
  fill: none;
  stroke-width: 6;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke-dasharray: 12, 500;
  stroke-dashoffset: 0;
  animation: lineMove 1s linear infinite;
  filter: url(#glow);
}

/* 水滴状电流 - 内核（更细更亮） */
.g-rect-fill-core {
  fill: none;
  stroke-width: 3;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke-dasharray: 8, 504;
  stroke-dashoffset: 0;
  animation: lineMove 1s linear infinite;
  opacity: 0.9;
}

@keyframes lineMove {
  0% {
    stroke-dashoffset: 512;
  }
  100% {
    stroke-dashoffset: 0;
  }
}

.line-label {
  font-size: 12px;
  fill: #303133;
  stroke: #ffffff;
  stroke-width: 0.5;
  paint-order: stroke;
}

.legend-panel {
  position: absolute;
  left: 16px;
  bottom: 16px;
  z-index: 30;
  min-width: 180px;
  background-color: rgba(30, 41, 59, 0.9);
  border: 1px solid rgba(100, 116, 139, 0.5);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  pointer-events: auto;
  backdrop-filter: blur(8px);
}

.legend-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #e2e8f0;
  font-size: 13px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.legend-row:last-child {
  margin-bottom: 0;
}

.legend-text {
  color: #cbd5e1;
}

.legend-line {
  width: 28px;
  height: 0;
  border-top-width: 3px;
  border-top-style: solid;
  filter: drop-shadow(0 0 4px currentColor);
}

.legend-line-safe {
  border-top-color: #4ade80; /* 安全：亮绿色 */
}

.legend-line-medium {
  border-top-color: #fbbf24; /* 中等：亮黄色 */
}

.legend-line-high {
  border-top-color: #fb923c; /* 接近最大：亮橙色 */
}

.legend-line-overload {
  border-top-color: #f87171; /* 过载：亮红色 */
}

.legend-line-switch-user {
  border-top-color: #60a5fa;
}

.chart-trigger-wrapper {
  position: absolute;
  right: 0;
  bottom: 16px;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background-color: #ffffff;
  border-top-left-radius: 20px;
  border-bottom-left-radius: 20px;
  border: 1px solid #d0d0d0;
  border-right: none;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  padding: 8px 6px 8px 12px;
  transition: opacity 0.3s, transform 0.3s;
  opacity: 1;
  pointer-events: auto;
  will-change: transform, opacity;
}

.chart-trigger-wrapper.hidden {
  opacity: 0;
  pointer-events: none;
  transform: translateX(100%);
}

.chart-trigger-wrapper:hover {
  box-shadow: 0 0 15px 5px rgba(65, 184, 131, 0.4), -2px 0 8px rgba(0, 0, 0, 0.1);
  background-color: #ffffff;
}

.chart-trigger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-trigger-icon {
  width: 20px;
  height: 20px;
  color: #41b883;
}

.chart-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px;
  max-height: 400px;
}

.chart-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  border-bottom: 1px solid #eee;
  padding-bottom: 8px;
  flex-shrink: 0;
}

.chart-main-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.chart-scroll-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 4px;
}

.chart-scroll-container::-webkit-scrollbar {
  width: 6px;
}

.chart-scroll-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.chart-scroll-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.chart-scroll-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.ai-loading-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background-color: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-continue-btn {
  color: #67c23a !important;
  transition: all 0.3s;
}

.ai-continue-btn:hover {
  background-color: #67c23a !important;
  border-color: #67c23a !important;
  color: #ffffff !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.4);
}

.chart-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.custom-loading {
  display: inline-flex;
  align-items: center;
}

.custom-loading .circular {
  margin-right: 6px;
  width: 18px;
  height: 18px;
  animation: loading-rotate 2s linear infinite;
}

.custom-loading .circular .path {
  animation: loading-dash 1.5s ease-in-out infinite;
  stroke-dasharray: 90, 150;
  stroke-dashoffset: 0;
  stroke-width: 2;
  stroke: var(--el-button-text-color);
  stroke-linecap: round;
}

/* 调度中状态 - 红色加载图标 */
.simulation-stop-btn.is-loading-state .custom-loading .circular .path {
  stroke: #f56c6c;
}

@keyframes loading-rotate {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes loading-dash {
  0% {
    stroke-dasharray: 1, 200;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -40px;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -120px;
  }
}

.chart-title {
  font-weight: 600;
  color: #303133;
}

.chart-container {
  width: 100%;
  height: 140px;
}

.chart-container-line {
  height: 120px;
}

.param-row {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.param-row.param-chart-row {
  flex-direction: column;
  align-items: stretch;
  margin-bottom: 12px;
}

.param-label {
  width: 120px;
  font-size: 14px;
  color: #000000;
}

.param-ai-answer {
  flex: 1;
  font-size: 12px;
  color: #000000;
  max-height: 120px;
  overflow: auto;
  border: 1px solid #d0d0d0;
  padding: 4px 6px;
  border-radius: 2px;
  white-space: pre-wrap;
}

.transformer-status {
  font-size: 12px;
  margin-left: 4px;
}

.transformer-status.active {
  color: #67c23a;
}

.transformer-status.standby {
  color: #909399;
}

.ai-buttons-row {
  display: flex;
  gap: 8px;
}

/* 仿真引擎控制行样式 */
.simulation-control-row {
  flex-wrap: wrap;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e0e0e0;
}

.simulation-start-btn {
  color: #409eff !important;
  border-color: #409eff !important;
  background-color: rgba(64, 158, 255, 0.1) !important;
  transition: all 0.3s;
}

.simulation-start-btn:hover {
  background-color: #409eff !important;
  color: #ffffff !important;
  border-color: #409eff !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.4);
}

.simulation-start-btn .el-icon {
  color: #409eff !important;
}

.simulation-stop-btn {
  color: #f56c6c !important;
  border-color: #f56c6c !important;
  background-color: rgba(245, 108, 108, 0.1) !important;
  transition: all 0.3s;
}

.simulation-stop-btn:hover {
  background-color: #f56c6c !important;
  color: #ffffff !important;
  border-color: #f56c6c !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.4);
}

.simulation-stop-btn .el-icon {
  color: #f56c6c !important;
}

/* 调度中状态 - 红色 */
.simulation-stop-btn.is-loading-state {
  color: #f56c6c !important;
  border-color: #f56c6c !important;
  background-color: rgba(245, 108, 108, 0.1) !important;
}

.simulation-stop-btn.is-loading-state .el-icon {
  color: #f56c6c !important;
}

.simulation-pause-btn {
  transition: all 0.3s;
}

.simulation-pause-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

/* 暂停仿真状态 - 黄色 */
.simulation-pause-btn.is-running {
  color: #e6a23c !important;
  border-color: #e6a23c !important;
  background-color: rgba(230, 162, 60, 0.1) !important;
}

.simulation-pause-btn.is-running .el-icon {
  color: #e6a23c !important;
}

.simulation-pause-btn.is-running:hover {
  background-color: #e6a23c !important;
  color: #ffffff !important;
  border-color: #e6a23c !important;
  box-shadow: 0 4px 16px rgba(230, 162, 60, 0.4);
}

/* 继续仿真状态 - 绿色 */
.simulation-pause-btn.is-paused {
  color: #67c23a !important;
  border-color: #67c23a !important;
  background-color: rgba(103, 194, 58, 0.1) !important;
}

.simulation-pause-btn.is-paused .el-icon {
  color: #67c23a !important;
}

.simulation-pause-btn.is-paused:hover {
  background-color: #67c23a !important;
  color: #ffffff !important;
  border-color: #67c23a !important;
  box-shadow: 0 4px 16px rgba(103, 194, 58, 0.4);
}

.simulation-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 8px;
  font-size: 13px;
  color: #606266;
}

.simulation-time {
  font-family: monospace;
  color: #909399;
}

/* 仿真配置对话框样式 */
.simulation-config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.config-label {
  font-size: 14px;
  color: #606266;
  min-width: 120px;
}

.config-preview {
  margin-top: 8px;
}

.flow-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}

.ai-dispatch-btn {
  color: #000000 !important;
  transition: all 0.3s;
}

.ai-dispatch-btn:hover {
  background-color: #000000 !important;
  color: #ffffff !important;
  border-color: #000000 !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

.ai-result-btn {
  color: #409eff !important;
  background-color: #ffffff !important;
  border-color: #409eff !important;
  transition: all 0.3s;
}

.ai-result-btn:hover {
  color: #ffffff !important;
  background-color: #409eff !important;
  border-color: #409eff !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

.ai-global-controls {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  transform-origin: top left;
}

.ai-global-error {
  color: #f56c6c;
  font-size: 12px;
}

/* 规划建议按钮 */
.planning-btn {
  color: #ffffff !important;
  background-color: #e6a23c !important;
  border-color: #e6a23c !important;
}

.planning-btn:hover {
  background-color: #c48a2e !important;
  border-color: #c48a2e !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.4);
}

/* 规划建议按钮行 */
.planning-buttons-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.planning-badge {
  margin-left: 4px;
}

/* 规划建议快速摘要 */
.planning-quick-summary {
  display: flex;
  flex-direction: column;
}

.quick-summary-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-summary-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-label {
  font-size: 13px;
  color: #606266;
}

.quick-value {
  font-size: 13px;
  font-weight: 500;
}

.quick-value.good {
  color: #67c23a;
}

.quick-value.warning {
  color: #e6a23c;
}

.quick-value.critical {
  color: #f56c6c;
}

/* 规划建议面板 */
.planning-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 500px;
  overflow: hidden;
}

.planning-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.planning-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.planning-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #909399;
  gap: 8px;
}

.planning-loading .is-loading {
  animation: rotating 2s linear infinite;
  font-size: 24px;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.planning-error {
  color: #f56c6c;
  text-align: center;
  padding: 20px;
}

.planning-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  max-height: 420px;
}

/* 系统状态概览 */
.planning-summary {
  display: flex;
  gap: 16px;
  padding: 12px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-label {
  font-size: 12px;
  color: #909399;
}

.summary-value {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.summary-value.good {
  color: #67c23a;
}

.summary-value.warning {
  color: #e6a23c;
}

.summary-value.critical {
  color: #f56c6c;
}

.summary-value.high {
  color: #f56c6c;
}

/* 建议列表 */
.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.suggestion-item {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: #ffffff;
  transition: all 0.2s;
}

.suggestion-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.suggestion-item.high {
  border-left: 3px solid #f56c6c;
  background: linear-gradient(90deg, #fef0f0 0%, #ffffff 20%);
}

.suggestion-item.medium {
  border-left: 3px solid #e6a23c;
  background: linear-gradient(90deg, #fdf6ec 0%, #ffffff 20%);
}

.suggestion-item.low {
  border-left: 3px solid #67c23a;
  background: linear-gradient(90deg, #f0f9eb 0%, #ffffff 20%);
}

.suggestion-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.suggestion-icon {
  font-size: 16px;
}

.suggestion-title {
  flex: 1;
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.suggestion-priority {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  color: #ffffff;
  font-weight: 500;
}

.suggestion-desc {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
  line-height: 1.5;
}

.suggestion-recommendation {
  font-size: 12px;
  color: #409eff;
  background: #ecf5ff;
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.suggestion-action {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
  display: flex;
  justify-content: flex-end;
}

.suggestion-applied-item {
  opacity: 0.7;
  background-color: #f5f5f5 !important;
}

.suggestion-applied-item .suggestion-header {
  opacity: 0.8;
}

.suggestion-applied {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
  display: flex;
  justify-content: flex-end;
  color: #67c23a;
  font-size: 13px;
  font-weight: 500;
}

.suggestion-details {
  margin-top: 8px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
}

.detail-title {
  font-weight: 500;
  color: #606266;
  margin-bottom: 4px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  color: #606266;
}

.need-connection {
  font-size: 11px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 2px 6px;
  border-radius: 4px;
}

.no-suggestions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #67c23a;
  gap: 8px;
}

.no-suggestions .el-icon {
  font-size: 32px;
}

.ai-global-result-body {
  padding: 8px;
  font-size: 12px;
  max-height: 220px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-section {
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 6px;
}

.ai-section:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.ai-section-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #303133;
}

.ai-section-row {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 2px;
}

.ai-section-row span {
  flex: 1;
}

.ai-item-row {
  margin-bottom: 4px;
}

.ai-item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ai-item-name {
  font-size: 12px;
  font-weight: 500;
  color: #409eff;
}

.ai-item-line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ai-item-line span {
  font-size: 12px;
}

.ai-raw-json {
  margin: 0;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow: auto;
  border: 1px solid #f0f0f0;
  padding: 4px;
  border-radius: 2px;
  background-color: #fafafa;
}

.param-input {
  flex: 1;
  font-size: 14px;
  padding: 6px 8px;
  border: 1px solid #d0d0d0;
  border-radius: 2px;
}

.param-name-input {
  border: none;
  background-color: transparent;
}

.param-name-input:focus {
  border: 1px solid #409eff;
  background-color: #fafafa;
}

.param-slider {
  flex: 1;
  margin-left: 4px;
}

.param-value {
  flex: 1;
  font-size: 14px;
  color: #303133;
  padding: 6px 0;
  margin-top: 8px;
}

.param-row input[type='checkbox'] {
  width: 18px;
  height: 18px;
  margin-right: 8px;
}

.param-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

/* 负荷曲线图表样式 */
.load-profile-chart {
  width: 100%;
  height: 250px;
  margin-top: 8px;
}

.param-chart-row {
  flex-direction: column;
  align-items: stretch;
}

.chart-time-label {
  text-align: center;
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
}

.param-select {
  flex: 1;
}

.param-button {
  padding: 2px 10px;
  font-size: 13px;
  border-radius: 3px;
  border: 1px solid #d0d0d0;
  background-color: #f5f5f5;
  cursor: pointer;
}

.param-button:hover {
  background-color: #e9e9e9;
}

.clone {
  position: absolute;
  z-index: 2;
  cursor: grab;
}

.clone.highlighted {
  filter: drop-shadow(0 0 10px rgba(245, 158, 11, 0.7));
}

.connection-path.highlighted,
.connection-path-bg.highlighted {
  filter: drop-shadow(0 0 8px rgba(245, 158, 11, 0.8));
  stroke-width: 3px;
}

.g-rect-fill.highlighted,
.g-rect-fill-core.highlighted {
  filter: url(#glow-strong);
}

.clone-image {
  width: 80px;
  height: 80px;
  object-fit: contain;
}

.context-menu-content {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}

.menu-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  color: #303133;
  transition: background-color 0.2s;
}

.menu-item:hover {
  background-color: #f5f7fa;
}

.context-menu-divider {
  margin: 6px 0;
}

.context-menu-title {
  padding: 4px 12px;
  font-size: 12px;
  color: #909399;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
