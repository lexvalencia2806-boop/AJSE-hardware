(() => {
  "use strict";

  const API_BASE = ["localhost", "127.0.0.1"].includes(location.hostname)
    && location.port !== "5000"
    ? "http://127.0.0.1:5000"
    : "";
  const STORAGE = {
    cart: "nexus-hardware-cart-v1",
    requests: "nexus-hardware-requests-v1",
    interests: "nexus-hardware-interests-v1",
  };
  // Prefijo de los números de pedido simulados. Cámbialo si decides otro nombre de marca.
  const ORDER_PREFIX = "AJSE";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const money = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  });
  const PRODUCT_SPECS = {
    "lap-lenovo-slim3": ["Portátil Lenovo IdeaPad Slim 3; la generación, pantalla, memoria y procesador cambian según SKU.", "Confirma la referencia completa, memoria ampliable, almacenamiento y si incluye Windows con licencia."],
    "lap-asus-vivobook-15": ["Portátil ASUS VivoBook de familia 15; existen configuraciones diferentes de procesador, pantalla y memoria.", "Verifica el número de modelo, RAM, SSD, conexiones y sistema operativo antes de elegir."],
    "lap-hp-pavilion-14": ["Portátil HP Pavilion de familia 14; las especificaciones dependen de la generación y referencia.", "Confirma procesador, memoria, almacenamiento, puertos y licencia de Windows del SKU publicado."],
    "lap-acer-nitro-v": ["Portátil de la familia Acer Nitro V orientado a gaming; GPU, pantalla y procesador varían por modelo exacto.", "Revisa la referencia de GPU, memoria, refrigeración, adaptador de corriente y requisitos de los juegos."],
    "cel-samsung-a55": ["Smartphone Samsung Galaxy A55 con plataforma Android; versión del sistema y actualizaciones dependen de la región.", "Confirma almacenamiento, memoria, bandas de red, estado de batería y garantía local."],
    "cel-motorola-edge-50": ["Smartphone Motorola Edge 50 de la familia Android; las variantes regionales pueden cambiar.", "Verifica capacidad, bandas de operador, NFC, accesorios y soporte de actualizaciones de la variante."],
    "cel-iphone-15": ["Smartphone Apple iPhone 15 con sistema iOS; versión, capacidad y región dependen de la unidad.", "Verifica almacenamiento, estado de batería, bloqueo de operador, autenticidad y cobertura de garantía."],
    "tab-ipad-10": ["Apple iPad (10.ª generación) con sistema iPadOS; accesorios compatibles deben coincidir con esta generación.", "Confirma almacenamiento, conectividad Wi-Fi o celular y compatibilidad exacta de Apple Pencil y teclado."],
    "tab-samsung-s9fe": ["Samsung Galaxy Tab S9 FE con Android; versión regional, conectividad y accesorios pueden variar.", "Comprueba almacenamiento, conectividad, compatibilidad del S Pen y garantía."],
    "gpu-rtx-4060": ["GPU NVIDIA GeForce RTX 4060; el fabricante de la tarjeta determina memoria, tamaño y conectores exactos.", "Requiere PC con ranura PCIe x16 y fuente que cumpla conectores y potencia recomendados para la variante."],
    "gpu-rtx-4070-super": ["GPU NVIDIA GeForce RTX 4070 SUPER; tamaño, consumo y alimentación varían por fabricante.", "Comprueba espacio libre del gabinete, conectores de alimentación y fuente recomendada antes de instalar."],
    "mb-msi-b550": ["Placa madre MSI B550M PRO-VDH, formato micro-ATX, socket AM4 y memoria DDR4.", "El soporte de CPU depende de la lista del fabricante y de la versión de BIOS; no admite procesadores AM5 ni memoria DDR5."],
    "ssd-samsung-980-1tb": ["SSD Samsung 980 de 1 TB, formato M.2 2280 NVMe PCIe 3.0 x4.", "Comprueba que el equipo tenga ranura M.2 NVMe disponible; la velocidad final depende de la plataforma."],
    "ram-corsair-vengeance-16": ["Memoria de escritorio Corsair Vengeance DDR4 de 16 GB; velocidad y distribución dependen del kit exacto.", "La placa y el procesador deben admitir DDR4; no es compatible con ranuras DDR5 ni memorias de portátil SO-DIMM."],
    "cpu-amd-ryzen-5-5600": ["Procesador AMD Ryzen 5 5600 de escritorio, socket AM4.", "Usa placa madre AM4 con BIOS compatible y memoria DDR4. Comprueba refrigeración incluida en la referencia exacta."],
    "cpu-amd-ryzen-7-5700x": ["Procesador AMD Ryzen 7 5700X de escritorio, familia Ryzen 5000 y socket AM4.", "Usa una placa AM4 con BIOS compatible y DDR4. Comprueba la solución térmica: no supongas que incluye cooler."],
    "cpu-amd-ryzen-5-7600": ["Procesador AMD Ryzen 5 7600 de escritorio, familia Ryzen 7000 y socket AM5.", "Usa placa AM5 y memoria DDR5. Confirma si la unidad incluye disipador y si la BIOS de la placa lo admite."],
    "cpu-intel-core-i5-12400f": ["Procesador Intel Core i5-12400F de 12.ª generación, socket LGA1700.", "La variante F necesita una tarjeta gráfica dedicada. La placa debe ser LGA1700 y admitir la generación del procesador."],
    "mb-asus-tuf-b650m": ["Placa madre ASUS TUF Gaming B650M-PLUS, socket AM5 y memoria DDR5.", "Requiere procesador AMD compatible con AM5 y memoria DDR5. Comprueba BIOS, formato micro-ATX y espacio en el gabinete."],
    "mb-msi-pro-b760m": ["Placa MSI PRO B760M-A WIFI DDR4, chipset B760, socket LGA1700 y memoria DDR4.", "Admite procesadores Intel compatibles con LGA1700 según la lista de soporte y BIOS. Esta variante DDR4 no usa memoria DDR5."],
    "ram-kingston-fury-ddr5-32": ["Memoria Kingston Fury Beast DDR5 de 32 GB para equipos de escritorio.", "La placa debe usar DDR5. Confirma velocidad, número de módulos y perfil admitido para activar EXPO/XMP."],
    "psu-corsair-cx650": ["Fuente Corsair CX650 de 650 W de formato ATX; comprueba revisión y certificación en la etiqueta del producto.", "Verifica consumo del equipo, conectores de placa/GPU y espacio del chasis. No mezcles cables modulares de otras fuentes."],
    "case-deepcool-cc560": ["Gabinete DeepCool CC560 para montaje de escritorio; comprueba variante y ventiladores incluidos.", "Confirma soporte del formato de placa, longitud de GPU, altura del cooler y espacio para radiadores."],
    "cooler-cooler-master-hyper-212": ["Disipador por aire Cooler Master Hyper 212; el kit de montaje y sockets admitidos dependen de la revisión.", "Confirma compatibilidad con socket y altura del gabinete; revisa el kit de instalación incluido."],
    "ssd-wd-blue-sn580-1tb": ["SSD WD Blue SN580 de 1 TB, formato M.2 2280 NVMe PCIe 4.0.", "Requiere ranura M.2 compatible con NVMe; puede operar a menor velocidad si la plataforma es de otra generación."],
    "gpu-amd-rx-7600": ["GPU AMD Radeon RX 7600 de 8 GB; dimensiones y conectores dependen del fabricante de la tarjeta.", "Requiere ranura PCIe x16; comprueba espacio del gabinete, conectores y potencia de la fuente para ese modelo."],
    "monitor-lg-24": ["Monitor LG IPS de 24 pulgadas; resolución, frecuencia de refresco y puertos cambian según referencia.", "Confirma entradas HDMI/DisplayPort disponibles y que coincidan con la salida del computador o adaptador."],
    "teclado-logitech-mx": ["Teclado Logitech MX Keys Mini inalámbrico; distribución física de teclas puede depender de la región.", "Verifica el idioma del teclado y compatibilidad Bluetooth o del receptor con el sistema operativo."],
    "mouse-logitech-g502": ["Mouse Logitech G502 HERO con conexión USB; funciones avanzadas pueden requerir Logitech G HUB.", "Comprueba espacio disponible en USB y descarga software únicamente desde el sitio oficial de Logitech."],
    "audifonos-hyperx-cloud": ["Audífonos HyperX Cloud Stinger 2; conexión y controles varían según la edición.", "Verifica si el conector requerido es de 3,5 mm o USB y la compatibilidad con consola, PC o móvil."],
    "consola-ps5-slim": ["Consola Sony PlayStation 5 Slim con sistema PlayStation; la edición puede ser digital o con lector.", "Comprueba edición, región, espacio, accesorios y suscripción requerida para funciones en línea."],
    "consola-nintendo-switch-oled": ["Consola Nintendo Switch OLED con software Nintendo Switch; puede usarse portátil o en base.", "Verifica versión regional, contenido incluido, capacidad de almacenamiento y compatibilidad de juegos/accesorios."],
    "impresora-epson-l3250": ["Multifuncional Epson EcoTank L3250 de impresión, copia y escaneo; conectividad depende de la configuración.", "Requiere tinta Epson adecuada, papel y controlador oficial para tu sistema operativo; confirma conexión Wi-Fi/USB."],
    "repuesto-cargador-universal": ["Cargador USB-C de referencia de hasta 65 W; no es universal para todos los portátiles.", "El dispositivo debe admitir carga USB-C Power Delivery y requerir como máximo la potencia compatible; valida voltaje y perfil."],
  };
  const CATEGORY_GUIDES = {
    "Portátiles": {
      system: "Sistema: Windows o Linux según la configuración exacta; confirma sistema incluido, edición y licencia. Es un equipo integrado: procesador, memoria, almacenamiento, pantalla y batería forman parte del portátil.",
      compatibility: "Comprueba la referencia completa, CPU, RAM, SSD, resolución de pantalla, puertos, Wi-Fi, cargador y garantía. Las variantes del mismo nombre comercial pueden ser distintas.",
      guide: ["Confirma la configuración completa y que incluya el cargador original o compatible.", "Al encenderlo, elige idioma, región, red y cuenta; no compartas tu contraseña con el vendedor.", "Instala actualizaciones de sistema y controladores desde Windows Update o la página oficial del fabricante.", "Activa seguridad de pantalla/cifrado si está disponible y crea una copia de seguridad.", "Comprueba batería, puertos, cámara y teclado durante el periodo de devolución."]
    },
    "Celulares": {
      system: "Sistema móvil: Android en Samsung/Motorola e iOS en iPhone. La versión y el periodo de actualizaciones varían con región y referencia.",
      compatibility: "Verifica desbloqueo de operador, bandas de red locales, SIM/eSIM, almacenamiento, cargador, estado de batería y garantía.",
      guide: ["Confirma que el equipo esté libre de cuentas, bloqueos y operador antes de transferir tus datos.", "Inserta SIM o activa eSIM siguiendo las instrucciones de tu operador.", "Configura bloqueo seguro, recuperación de cuenta y actualizaciones automáticas.", "Instala aplicaciones desde la tienda oficial del sistema y activa copias de seguridad.", "Prueba cámaras, micrófono, altavoz, carga, Wi-Fi y red móvil."]
    },
    "Tabletas": {
      system: "Sistema: iPadOS para iPad y Android para Galaxy Tab. Aplicaciones, actualizaciones y accesorios compatibles dependen de la generación.",
      compatibility: "Verifica almacenamiento, versión Wi-Fi/celular, cargador, compatibilidad de lápiz digital/teclado y disponibilidad de actualizaciones.",
      guide: ["Identifica la generación exacta en Ajustes y confirma accesorios compatibles.", "Conecta a Wi-Fi, inicia sesión en tu cuenta y aplica las actualizaciones del sistema.", "Configura bloqueo de pantalla, copias de seguridad y controles de privacidad.", "Instala aplicaciones desde App Store o Google Play y prueba lápiz, teclado y audio."]
    },
    "Componentes": {
      system: "Componente para PC de escritorio: por sí solo no ejecuta Windows ni incluye un computador completo. Se integra en un sistema compatible que normalmente usa Windows o Linux.",
      compatibility: "Antes de comprar, cruza socket y generación de CPU, placa madre y BIOS, tipo DDR de RAM, ranuras de almacenamiento, tamaño del gabinete, conexiones y consumo de la fuente. DDR4 y DDR5 no son intercambiables.",
      guide: ["Elige una sola plataforma compatible: AM4 (Ryzen 5 5600/7 5700X + B550M + DDR4), AM5 (Ryzen 5 7600 + B650M + DDR5) o Intel LGA1700 (i5-12400F + B760M DDR4 + tarjeta gráfica dedicada). No mezcles sockets ni DDR4/DDR5.", "Comprueba el tamaño de la placa, GPU y disipador contra el gabinete, y calcula el consumo total frente a los conectores y potencia de la fuente.", "Apaga y desconecta todo; trabaja sobre una superficie limpia y descarga electricidad estática.", "Monta procesador, RAM y SSD siguiendo los manuales; alinea las marcas y nunca fuerces sockets o ranuras.", "Fija placa y fuente, instala disipador y tarjeta gráfica, y conecta los cables de alimentación según los manuales.", "Revisa ventiladores, conexión del panel frontal y que ningún cable toque las aspas; cierra el gabinete.", "Enciende y confirma que la CPU, memoria y unidades aparezcan en BIOS/UEFI; configura arranque y perfiles de memoria solo si son compatibles.", "Instala Windows o Linux desde medios oficiales, aplica actualizaciones y descarga drivers de los fabricantes."]
    },
    "Periféricos": {
      system: "Accesorio externo para computador o consola; no ejecuta un sistema operativo propio. Funciones adicionales pueden depender de software del fabricante.",
      compatibility: "Comprueba conexión USB, Bluetooth o audio, puertos disponibles, sistema operativo, distribución de teclado y compatibilidad con la consola.",
      guide: ["Revisa conectores, cables, fuente y accesorios incluidos en la referencia exacta.", "Conecta directamente al puerto recomendado o realiza el emparejamiento Bluetooth desde el sistema.", "Instala software solo si se necesitan funciones adicionales y descárgalo de la web oficial.", "Prueba todas las entradas, teclas, botones, audio y controles antes de instalarlo en el puesto definitivo."]
    },
    "Videojuegos": {
      system: {
        "consola-ps5-slim": "Consola con sistema PlayStation 5; formato Slim. Los modelos con o sin lector de discos son referencias distintas.",
        "consola-nintendo-switch-oled": "Consola con sistema Nintendo Switch; funciona en modo portátil o conectada al televisor mediante la base."
      },
      compatibility: "Verifica edición y región, espacio de almacenamiento, formato físico/digital, accesorios incluidos y requisitos de suscripciones en línea.",
      guide: ["Conecta el adaptador y, si aplica, la base a una pantalla compatible.", "Configura idioma, red y cuenta personal; activa seguridad de cuenta.", "Actualiza el software desde los ajustes oficiales de la consola.", "Instala juegos de fuente autorizada y configura controles parentales cuando corresponda."]
    },
    "Impresión": {
      system: "Impresora multifuncional para impresión y escaneo; funciona mediante el controlador compatible con el sistema operativo del computador.",
      compatibility: "Revisa sistema operativo, conexión USB/Wi-Fi, consumibles correctos, tamaño de papel y disponibilidad de controladores oficiales.",
      guide: ["Retira protecciones y coloca la impresora en una superficie nivelada.", "Usa solo tinta y consumibles compatibles; llena tanques siguiendo el manual del fabricante.", "Instala el controlador desde el sitio oficial y conecta por USB o a la misma red Wi-Fi.", "Ejecuta alineación y prueba de inyectores antes de imprimir documentos importantes.", "Mantén el equipo encendido y úsalo según las recomendaciones para evitar que la tinta se seque."]
    },
    "Repuestos": {
      system: "Accesorio o repuesto: no tiene un sistema operativo independiente. Su funcionamiento depende del equipo principal y de que las especificaciones eléctricas y físicas coincidan.",
      compatibility: "Confirma modelo del dispositivo, voltaje, amperaje, potencia, conector y protocolos de carga. No lo conectes si las especificaciones no coinciden.",
      guide: ["Lee la etiqueta del equipo original y compara voltaje, corriente, potencia y polaridad cuando aplique.", "Confirma el protocolo de carga y conector admitidos por el fabricante del dispositivo.", "Conecta primero el accesorio al dispositivo y utiliza una toma segura; no cubras cargadores.", "Desconéctalo ante calor excesivo, ruido, olor o daño del cable."]
    }
  };
  const state = {
    products: [],
    requests: [],
    cart: readStoredCart(),
    interests: readStoredInterests(),
    category: "Todos",
    search: "",
    sort: "featured",
    approvalFilter: "all",
    adminStatusLoaded: false,
    adminBackendAvailable: false,
    adminConfigured: false,
    adminAuthenticated: false,
    csrfToken: "",
    storePaymentReady: false,
    storePublicKey: "",
    paymentBrick: null,
    checkoutOrder: null,
    checkoutFormValues: null,
    checkoutMode: null,
    simulatedOrder: null,
    storeStatusLoaded: false,
    aiConfigured: false,
    aiStatusLoaded: false,
    sending: false,
  };

  function readStorage(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key));
      return value ?? fallback;
    } catch (error) {
      console.warn(`No se pudo leer el almacenamiento local (${key}).`, error);
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      console.error(`No se pudo guardar la información local (${key}).`, error);
      showToast("No se pudieron guardar los cambios en este navegador.", "error");
      return false;
    }
  }

  function readStoredCart() {
    const value = readStorage(STORAGE.cart, {});
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([, quantity]) =>
      Number.isInteger(quantity) && quantity >= 1 && quantity <= 20));
  }

  function readStoredInterests() {
    const value = readStorage(STORAGE.interests, {});
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([, count]) =>
      Number.isFinite(count) && count > 0));
  }

  function readStoredRequests() {
    const value = readStorage(STORAGE.requests, []);
    if (!Array.isArray(value)) return [];
    return value.filter(isValidRequest);
  }

  function isValidRequest(item) {
    return item
      && typeof item === "object"
      && typeof item.id === "string"
      && item.id.length > 0
      && typeof item.client === "string"
      && typeof item.created_at === "string"
      && Number.isFinite(Date.parse(item.created_at))
      && Number.isFinite(item.total)
      && item.total >= 0
      && ["pending", "approved", "rejected"].includes(item.status)
      && Array.isArray(item.items)
      && item.items.length > 0
      && item.items.every((product) =>
        product
        && typeof product.product_id === "string"
        && typeof product.name === "string"
        && Number.isInteger(product.quantity)
        && product.quantity >= 1
        && product.quantity <= 20
        && Number.isFinite(product.unit_price)
        && product.unit_price >= 0);
  }

  async function fetchApi(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(state.csrfToken ? { "X-CSRF-Token": state.csrfToken } : {}),
        ...options.headers,
      },
    });
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      if (response.ok) {
        const parseError = new Error("El servidor devolvió una respuesta no válida.");
        parseError.status = response.status;
        throw parseError;
      }
      payload = {};
    }
    if (!payload || typeof payload !== "object") payload = {};
    if (!response.ok) {
      const requestError = new Error(payload.error || `La solicitud falló (${response.status}).`);
      requestError.status = response.status;
      throw requestError;
    }
    return payload;
  }

  function showToast(message, type = "success") {
    const region = $("#toastRegion");
    if (!region) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    region.append(toast);
    window.setTimeout(() => toast.remove(), 3600);
  }

  function getProduct(productId) {
    return state.products.find((product) => product.id === productId);
  }

  function productSearchText(product) {
    return normalizeText([
      product.name,
      product.category,
      product.subtitle,
      product.description,
      ...(PRODUCT_SPECS[product.id] || []),
    ].join(" "));
  }

  function fallbackImage(product) {
    const safeName = product.name
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .slice(0, 48);
    const safeCategory = product.category
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .slice(0, 30);
    const artwork = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#203d4a"/><stop offset="1" stop-color="#15243b"/></linearGradient><linearGradient id="a"><stop stop-color="#a6f6d1"/><stop offset="1" stop-color="#70a9ff"/></linearGradient><pattern id="p" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0v32" fill="none" stroke="#b8d8e8" stroke-opacity=".06"/></pattern></defs><rect width="900" height="520" fill="url(#g)"/><rect width="900" height="520" fill="url(#p)"/><circle cx="450" cy="205" r="106" fill="#9bf4cb" fill-opacity=".07"/><rect x="362" y="123" width="176" height="146" rx="30" fill="#9bf4cb" fill-opacity=".08" stroke="url(#a)" stroke-opacity=".75" stroke-width="3"/><path d="M411 221v-51h13l53 36v-36h13v51h-13l-53-36v36z" fill="url(#a)"/><text x="450" y="337" fill="#f1f6ff" font-family="Arial,sans-serif" font-size="27" font-weight="700" text-anchor="middle">${safeName}</text><text x="450" y="376" fill="#a6f6d1" font-family="Arial,sans-serif" font-size="17" letter-spacing="3" text-anchor="middle">${safeCategory.toLocaleUpperCase("es")}</text><text x="450" y="446" fill="#8fa1b5" font-family="Arial,sans-serif" font-size="14" letter-spacing="4" text-anchor="middle">NEXUS HARDWARE</text></svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(artwork)}`;
  }

  function useProductImage(image, product) {
    image.src = product.image;
    image.addEventListener("error", () => {
      image.classList.add("is-fallback");
      image.src = fallbackImage(product);
    }, { once: true });
  }

  function visibleProducts() {
    let products = state.products.filter((product) => {
      const matchesCategory = state.category === "Todos" || product.category === state.category;
      const query = normalizeText(state.search);
      const searchable = productSearchText(product);
      return matchesCategory && searchable.includes(query);
    });

    if (state.sort === "price-low") products = products.sort((a, b) => a.price - b.price);
    if (state.sort === "price-high") products = products.sort((a, b) => b.price - a.price);
    return products;
  }

  function renderProducts() {
    const grid = $("#productGrid");
    const template = $("#productTemplate");
    if (!grid || !template) return;
    const products = visibleProducts();
    grid.replaceChildren();
    products.forEach((product) => {
      const card = template.content.firstElementChild.cloneNode(true);
      const image = $(".product-image", card);
      useProductImage(image, product);
      image.alt = product.name;
      $(".product-badge", card).textContent = product.badge || "";
      $(".product-badge", card).hidden = !product.badge;
      $(".product-category", card).textContent = product.category;
      $(".product-name", card).textContent = product.name;
      $(".product-subtitle", card).textContent = product.subtitle;
      $(".stock-label", card).textContent = "Disponibilidad no verificada";
      $(".product-price", card).textContent = money.format(product.price);
      $(".product-price", card).title = "Precio referencial; no confirmado con un proveedor.";
      $$("[data-add-product]", card).forEach((button) => {
        button.dataset.addProduct = product.id;
      });
      card.querySelector("[data-product-details]").dataset.productDetails = product.id;
      grid.append(card);
    });

    $("#resultsLabel").textContent = products.length
      ? `Mostrando ${products.length} ${products.length === 1 ? "producto" : "productos"}`
      : "Sin resultados para esta búsqueda";
    $("#emptyCatalog").classList.toggle("hidden", products.length > 0);
    $("#heroProductCount").textContent = state.products.length;
    $("#heroCategoryCount").textContent = new Set(state.products.map((product) => product.category)).size;
    $("#allCategoryCount").textContent = state.products.length;
  }

  function fillList(container, values, elementName = "li") {
    const fragment = document.createDocumentFragment();
    values.forEach((value) => {
      const item = document.createElement(elementName);
      item.textContent = value;
      fragment.append(item);
    });
    container.replaceChildren(fragment);
  }

  function renderProductDetails(productId) {
    const product = getProduct(productId);
    if (!product) return;
    const guide = CATEGORY_GUIDES[product.category];
    if (!guide) {
      showToast("No se encontró una guía para este producto.", "error");
      return;
    }
    const system = typeof guide.system === "string"
      ? guide.system
      : guide.system[product.id] || `Sistema y funcionamiento propios de la categoría ${product.category.toLocaleLowerCase("es")}.`;
    const specificFacts = PRODUCT_SPECS[product.id] || [
      `${product.name}: ${product.description}`,
      "NEXUS aún no ha verificado esta referencia ni sus especificaciones para venta.",
    ];
    $("#detailCategory").textContent = `${product.category} · GUÍA DEL PRODUCTO`;
    $("#detailTitle").textContent = product.name;
    $("#detailSubtitle").textContent = product.subtitle;
    $("#detailDescription").textContent = product.description;
    $("#detailSystem").textContent = `${system} ${specificFacts[0]}`;
    $("#detailCompatibility").textContent = `${specificFacts[1]} ${guide.compatibility}`;
    $("#detailPrice").textContent = money.format(product.price);
    $("#detailAdd").dataset.addProduct = product.id;
    const image = $("#detailImage");
    image.alt = product.name;
    useProductImage(image, product);
    fillList($("#detailSpecs"), [
      `Referencia: ${product.name}`,
      `Categoría: ${product.category}`,
      ...specificFacts,
      `Uso previsto: ${product.description}`,
    ]);
    fillList($("#detailGuide"), guide.guide);
    setOverlay($("#productDetailsOverlay"), true);
  }

  function renderCart() {
    const items = Object.entries(state.cart)
      .map(([id, quantity]) => ({ product: getProduct(id), quantity }))
      .filter((entry) => entry.product && Number.isInteger(entry.quantity) && entry.quantity > 0);
    const count = items.reduce((sum, item) => sum + item.quantity, 0);
    const total = items.reduce((sum, item) => sum + item.product.price * item.quantity, 0);
    $("#cartCount").textContent = count;
    $("#drawerCartCount").textContent = count;
    $("#emptyCart").classList.toggle("hidden", items.length > 0);
    $("#cartSummary").classList.toggle("hidden", items.length === 0);
    $("#cartSubtotal").textContent = money.format(total);
    $("#formTotal").textContent = money.format(total);
    const container = $("#cartItems");
    container.replaceChildren();

    items.forEach(({ product, quantity }) => {
      const row = document.createElement("article");
      row.className = "cart-item";
      const photo = document.createElement("img");
      useProductImage(photo, product);
      photo.alt = "";
      photo.loading = "lazy";
      const details = document.createElement("div");
      details.className = "cart-item-details";
      const name = document.createElement("strong");
      name.textContent = product.name;
      const price = document.createElement("span");
      price.textContent = `${money.format(product.price)} × ${quantity} = ${money.format(product.price * quantity)}`;
      const controls = document.createElement("div");
      controls.className = "quantity-controls";
      controls.innerHTML = `<button type="button" data-quantity="-1" aria-label="Reducir cantidad">−</button><span>${quantity}</span><button type="button" data-quantity="1" aria-label="Aumentar cantidad">+</button>`;
      controls.dataset.productId = product.id;
      details.append(name, price, controls);
      row.append(photo, details);
      container.append(row);
    });
  }

  function renderStoreReadiness(status) {
    const readiness = $("#storeReadiness");
    const sandbox = status.configured === true && status.live_sales_enabled === false;
    const confirmed = Boolean(state.simulatedOrder);
    state.storePaymentReady = sandbox;
    state.storePublicKey = sandbox ? status.public_key : "";
    state.checkoutMode = sandbox ? "sandbox" : "simulated";
    if (!sandbox && Array.isArray(status.missing) && status.missing.length) {
      console.info("Checkout Sandbox de Mercado Pago sin configurar; se usa el modo simulado.", status.missing);
    }
    readiness.classList.add("store-ready");
    readiness.classList.remove("store-blocked");
    readiness.classList.toggle("hidden", confirmed);
    $("#storeReadinessTitle").textContent = sandbox
      ? "Checkout de prueba listo"
      : "Checkout de demostración activo";
    fillList($("#storeReadinessList"), sandbox
      ? ["Mercado Pago Sandbox activo · no se aceptan pagos reales.", "Catálogo y disponibilidad aún no están validados para venta."]
      : [
        "Pedido simulado: no se cobra dinero, no se reserva inventario y no se genera envío.",
        "El pago con tarjeta de prueba se activa cuando el servidor tenga credenciales Sandbox de Mercado Pago.",
      ]);
    $("#storeOrderForm").classList.toggle("hidden", confirmed || (sandbox && Boolean(state.checkoutOrder)));
    $("#storePaymentStep").classList.toggle("hidden", confirmed || !sandbox || !state.checkoutOrder);
    $("#storeConfirmation").classList.toggle("hidden", !confirmed);
    const submit = $("#startStorePayment");
    if (!submit.disabled) {
      submit.innerHTML = sandbox
        ? "Continuar al pago de prueba <span aria-hidden=\"true\">→</span>"
        : "Confirmar pedido de demostración <span aria-hidden=\"true\">→</span>";
    }
  }

  async function loadStoreStatus() {
    try {
      const status = await fetchApi("/api/store/status");
      renderStoreReadiness(status);
    } catch (error) {
      console.warn("No se pudo consultar la configuración del checkout.", error);
      renderStoreReadiness({
        configured: false,
        missing: [error.message],
        live_sales_enabled: false,
      });
    } finally {
      state.storeStatusLoaded = true;
    }
  }

  async function loadMercadoPagoSdk() {
    if (window.MercadoPago) return;
    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://sdk.mercadopago.com/js/v2";
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("No se pudo cargar el formulario seguro de Mercado Pago."));
      document.head.append(script);
    });
  }

  async function renderCardPaymentBrick() {
    if (!state.checkoutOrder || !state.storePaymentReady || state.paymentBrick) return;
    const result = $("#storePaymentResult");
    result.textContent = "Cargando el formulario seguro de Mercado Pago…";
    try {
      await loadMercadoPagoSdk();
      const mercadoPago = new window.MercadoPago(state.storePublicKey, { locale: "es-CO" });
      const bricksBuilder = mercadoPago.bricks();
      state.paymentBrick = await bricksBuilder.create(
        "cardPayment",
        "cardPaymentBrick_container",
        {
          initialization: { amount: state.checkoutOrder.total },
          callbacks: {
            onReady: () => { result.textContent = ""; },
            onSubmit: async (paymentData) => {
              result.textContent = "Procesando el pago de prueba…";
              try {
                const response = await fetchApi("/api/store/payments", {
                  method: "POST",
                  body: JSON.stringify({
                    order_id: state.checkoutOrder.id,
                    payment: paymentData,
                  }),
                });
                const messages = {
                  approved: "Pago de prueba aprobado por Mercado Pago. No se cobró dinero y no se enviará ningún producto.",
                  pending: "Pago de prueba pendiente de confirmación. No se cobró dinero.",
                  rejected: "Mercado Pago rechazó el pago de prueba. No se cobró dinero.",
                  cancelled: "El pago de prueba fue cancelado. No se cobró dinero.",
                  refunded: "El pago de prueba figura como reembolsado.",
                };
                result.textContent = messages[response.status] || "Mercado Pago recibió el pago de prueba.";
                if (response.status === "approved") {
                  state.cart = {};
                  writeStorage(STORAGE.cart, state.cart);
                  renderCart();
                }
                if (["rejected", "cancelled"].includes(response.status)) {
                  $("#restartStoreCheckout").classList.remove("hidden");
                }
                return response;
              } catch (error) {
                result.textContent = error.message || "No se pudo procesar el pago de prueba.";
                throw error;
              }
            },
            onError: (error) => {
              console.error("Mercado Pago reportó un error en el formulario de pago.", error);
              result.textContent = "El formulario seguro reportó un error. Recarga el checkout e inténtalo de nuevo.";
            },
          },
        },
      );
      result.textContent = "";
    } catch (error) {
      console.error("No se pudo iniciar el formulario de pago de Mercado Pago.", error);
      result.textContent = error.message || "No se pudo iniciar el formulario seguro de pago.";
    }
  }

  async function submitStoreOrder(event) {
    event.preventDefault();
    if (state.checkoutMode === "simulated") {
      await submitSimulatedOrder(event.currentTarget);
      return;
    }
    if (!state.storePaymentReady) {
      showToast("El checkout todavía no está habilitado para pruebas.", "error");
      return;
    }
    const items = Object.entries(state.cart)
      .filter(([id, quantity]) => getProduct(id) && quantity > 0)
      .map(([product_id, quantity]) => ({ product_id, quantity }));
    if (!items.length) {
      showToast("Agrega al menos un producto antes de continuar.", "error");
      return;
    }
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(
      ["client", "email", "phone", "address", "city", "note"]
        .map((field) => [field, String(data.get(field) || "").trim()]),
    );
    payload.items = items;
    const button = $("#startStorePayment");
    button.disabled = true;
    button.textContent = "Preparando checkout seguro…";
    try {
      const response = await fetchApi("/api/store/orders", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.checkoutFormValues = payload;
      state.checkoutOrder = response.order;
      $("#storeOrderTotal").textContent = money.format(response.order.total);
      $("#storePaymentResult").textContent = "";
      $("#restartStoreCheckout").classList.add("hidden");
      renderStoreReadiness({
        configured: true,
        public_key: state.storePublicKey,
        live_sales_enabled: false,
      });
      await renderCardPaymentBrick();
    } catch (error) {
      showToast(error.message || "No se pudo preparar el checkout.", "error");
    } finally {
      button.disabled = false;
      button.innerHTML = "Continuar al pago de prueba <span>→</span>";
    }
  }

  function createOrderNumber() {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, "0");
    const day = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
    const suffix = Math.random().toString(36).slice(2, 6).toUpperCase().padEnd(4, "0");
    return `${ORDER_PREFIX}-${day}-${suffix}`;
  }

  async function submitSimulatedOrder(form) {
    const cartItems = Object.entries(state.cart)
      .filter(([id, quantity]) => getProduct(id) && quantity > 0)
      .map(([product_id, quantity]) => ({ product_id, quantity }));
    if (!cartItems.length) {
      showToast("Agrega al menos un producto antes de continuar.", "error");
      return;
    }
    const data = new FormData(form);
    const customer = Object.fromEntries(
      ["client", "email", "phone", "address", "city", "note"]
        .map((field) => [field, String(data.get(field) || "").trim()]),
    );
    const number = createOrderNumber();
    const noteParts = [
      `Pedido simulado ${number}`,
      `Tel: ${customer.phone}`,
      `Entrega: ${customer.address}, ${customer.city}`,
    ];
    if (customer.note) noteParts.push(`Nota: ${customer.note}`);
    const payload = {
      client: customer.client,
      email: customer.email,
      note: noteParts.join(" · ").slice(0, 500),
      items: cartItems,
    };
    const items = cartItems.map(({ product_id, quantity }) => {
      const product = getProduct(product_id);
      return { product_id, name: product.name, quantity, unit_price: product.price };
    });
    const total = items.reduce((sum, item) => sum + item.unit_price * item.quantity, 0);
    const button = $("#startStorePayment");
    button.disabled = true;
    button.textContent = "Registrando pedido…";
    try {
      let created;
      let savedLocally = false;
      try {
        created = await fetchApi("/api/requests", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (error) {
        if (error.status) throw error;
        created = {
          ...payload,
          id: crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          items,
          total,
          status: "pending",
          created_at: new Date().toISOString(),
        };
        savedLocally = true;
      }
      if (!state.requests.some((item) => item.id === created.id)) state.requests.unshift(created);
      if (savedLocally) writeStorage(STORAGE.requests, state.requests);
      state.simulatedOrder = {
        number,
        createdAt: created.created_at || new Date().toISOString(),
        customer,
        items,
        total: Number.isFinite(created.total) ? created.total : total,
      };
      state.cart = {};
      writeStorage(STORAGE.cart, state.cart);
      renderCart();
      renderRequests();
      renderApprovals();
      form.reset();
      renderStoreConfirmation();
      renderStoreReadiness({ configured: state.storePaymentReady, public_key: state.storePublicKey, live_sales_enabled: false });
      $("#storeCheckoutOverlay .modal-card").scrollTop = 0;
      showToast("Pedido de demostración registrado.");
      if (API_BASE && !savedLocally) void refreshRequests();
    } catch (error) {
      showToast(error.message || "No se pudo registrar el pedido.", "error");
    } finally {
      button.disabled = false;
      button.innerHTML = "Confirmar pedido de demostración <span aria-hidden=\"true\">→</span>";
    }
  }

  function renderStoreConfirmation() {
    const order = state.simulatedOrder;
    if (!order) return;
    const created = new Date(order.createdAt);
    const when = Number.isNaN(created.getTime()) ? new Date() : created;
    $("#confirmNumber").textContent = order.number;
    $("#confirmDate").textContent = new Intl.DateTimeFormat("es-CO", { dateStyle: "long", timeStyle: "short" }).format(when);
    $("#confirmCustomer").textContent = `${order.customer.client} · ${order.customer.email}`;
    $("#confirmAddress").textContent = `${order.customer.address}, ${order.customer.city} · Tel. ${order.customer.phone}`;
    $("#confirmTotal").textContent = money.format(order.total);
    $("#confirmItems").replaceChildren(...order.items.map((item) => {
      const row = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = `${item.name} × ${item.quantity}`;
      const amount = document.createElement("span");
      amount.textContent = money.format(item.unit_price * item.quantity);
      row.append(label, amount);
      return row;
    }));
  }

  async function restartStoreCheckout() {
    if (state.paymentBrick) {
      await state.paymentBrick.unmount();
      state.paymentBrick = null;
    }
    state.checkoutOrder = null;
    $("#cardPaymentBrick_container").replaceChildren();
    $("#storePaymentResult").textContent = "";
    $("#restartStoreCheckout").classList.add("hidden");
    if (state.checkoutFormValues) {
      Object.entries(state.checkoutFormValues).forEach(([field, value]) => {
        if (field !== "items" && $("#storeOrderForm").elements[field]) {
          $("#storeOrderForm").elements[field].value = value;
        }
      });
    }
    if (state.storeStatusLoaded) {
      renderStoreReadiness({
        configured: state.storePaymentReady,
        public_key: state.storePublicKey,
        live_sales_enabled: false,
      });
    }
  }

  async function closeStoreCheckout() {
    if (state.paymentBrick) {
      try {
        await state.paymentBrick.unmount();
      } catch (error) {
        console.warn("No se pudo cerrar limpiamente el formulario de pago.", error);
      }
      state.paymentBrick = null;
      $("#cardPaymentBrick_container").replaceChildren();
    }
    setOverlay($("#storeCheckoutOverlay"), false);
  }

  function addToCart(productId) {
    if (state.checkoutOrder) {
      showToast("Termina o reinicia el checkout de prueba antes de cambiar el carrito.", "error");
      return;
    }
    const product = getProduct(productId);
    if (!product) return;
    state.cart[productId] = Math.min((state.cart[productId] || 0) + 1, 20);
    state.interests[product.category] = (state.interests[product.category] || 0) + 1;
    writeStorage(STORAGE.cart, state.cart);
    writeStorage(STORAGE.interests, state.interests);
    renderCart();
    renderRecommendation();
    showToast(`${product.name} se agregó al carrito.`);
  }

  function adjustQuantity(productId, amount) {
    if (state.checkoutOrder) {
      showToast("Termina o reinicia el checkout de prueba antes de cambiar el carrito.", "error");
      return;
    }
    const quantity = (state.cart[productId] || 0) + amount;
    if (quantity <= 0) delete state.cart[productId];
    else state.cart[productId] = Math.min(quantity, 20);
    writeStorage(STORAGE.cart, state.cart);
    renderCart();
  }

  function renderRecommendation() {
    if (!state.products.length) return;
    const preferredCategory = Object.entries(state.interests)
      .sort((a, b) => b[1] - a[1])[0]?.[0];
    const cartCategories = Object.keys(state.cart)
      .map((id) => getProduct(id)?.category)
      .filter(Boolean);
    const category = preferredCategory || cartCategories[0];
    const candidates = state.products
      .filter((product) => !state.cart[product.id])
      .sort((a, b) => {
        const aMatch = a.category === category ? 1 : 0;
        const bMatch = b.category === category ? 1 : 0;
        return bMatch - aMatch || a.price - b.price;
      });
    const recommendation = candidates[0] || state.products[0];
    const quantity = Object.values(state.interests).reduce((sum, count) => sum + count, 0);
    $("#recommendationName").textContent = recommendation.name;
    $("#recommendationSubtitle").textContent = category
      ? `Una opción destacada de ${category}, según tu actividad en este navegador.`
      : "Una opción destacada del catálogo para empezar a explorar.";
    $("#recommendationPrice").textContent = money.format(recommendation.price);
    $("#recommendationAdd").dataset.addProduct = recommendation.id;
    $("#aiSummaryTitle").textContent = category
      ? `Tu interés apunta a ${category.toLocaleLowerCase("es")}`
      : "Explora y encuentra tu próximo equipo";
    $("#aiSummaryText").textContent = category
      ? `Priorizamos opciones de ${category.toLocaleLowerCase("es")} y equipos con buenas calificaciones. Esta recomendación se calcula en tu navegador.`
      : "Las recomendaciones locales se ajustarán a tus categorías favoritas, sin enviar tu actividad a servicios externos.";
    $("#aiConfidence").textContent = String(state.products.length);
    $("#aiBudget").textContent = quantity ? money.format(recommendation.price) : "Sin definir";
    const signals = $("#aiSignals");
    signals.replaceChildren();
    [
      `${state.products.length} productos en el catálogo`,
      category ? `Categoría de interés: ${category}` : "Aún no hay una categoría favorita",
      "Actividad e intereses se guardan solo en este navegador",
    ].forEach((signal) => {
      const item = document.createElement("li");
      item.textContent = signal;
      signals.append(item);
    });
  }

  function renderRequestCard(item, showDecisionButtons = false) {
    const card = document.createElement("article");
    card.className = "request-card";
    const heading = document.createElement("div");
    heading.className = "request-card-heading";
    const identity = document.createElement("div");
    const client = document.createElement("strong");
    client.textContent = item.client;
    const date = document.createElement("small");
    date.textContent = new Date(item.created_at).toLocaleString("es-CO", {
      dateStyle: "medium",
      timeStyle: "short",
    });
    identity.append(client, date);
    const status = document.createElement("span");
    status.className = `status-pill status-${item.status}`;
    status.textContent = { pending: "Pendiente", approved: "Aprobada", rejected: "Rechazada" }[item.status] || item.status;
    heading.append(identity, status);

    const details = document.createElement("div");
    details.className = "request-items";
    const paymentLabels = {
      pending: "Pago de prueba pendiente",
      approved: "Pago de prueba aprobado",
      rejected: "Pago de prueba rechazado",
      cancelled: "Checkout de prueba cancelado",
      refunded: "Pago de prueba reembolsado",
    };
    if (paymentLabels[item.payment_status]) {
      const payment = document.createElement("small");
      payment.className = "request-note";
      payment.textContent = paymentLabels[item.payment_status];
      details.append(payment);
    }
    if (item.address || item.city || item.phone) {
      const delivery = document.createElement("small");
      delivery.className = "request-note";
      delivery.textContent = [
        item.phone ? `Tel. ${item.phone}` : "",
        [item.address, item.city].filter(Boolean).join(", "),
      ].filter(Boolean).join(" · ");
      details.append(delivery);
    }
    (item.items || []).forEach((product) => {
      const row = document.createElement("div");
      const label = document.createElement("span");
      label.textContent = `${product.name} × ${product.quantity}`;
      const price = document.createElement("strong");
      price.textContent = money.format(product.unit_price * product.quantity);
      row.append(label, price);
      details.append(row);
    });
    const total = document.createElement("div");
    total.className = "request-total";
    total.innerHTML = "<span>Total estimado</span>";
    const totalPrice = document.createElement("strong");
    totalPrice.textContent = money.format(item.total);
    total.append(totalPrice);
    card.append(heading, details, total);
    if (item.note) {
      const note = document.createElement("p");
      note.className = "request-note";
      note.textContent = `Nota: ${item.note}`;
      card.append(note);
    }
    if (showDecisionButtons && item.status === "pending") {
      const actions = document.createElement("div");
      actions.className = "request-actions";
      [
        ["rejected", "secondary-button", "Rechazar"],
        ["approved", "primary-button", "Aprobar solicitud"],
      ].forEach(([decision, className, label]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = className;
        button.dataset.decision = decision;
        button.dataset.requestId = item.id;
        button.textContent = label;
        actions.append(button);
      });
      card.append(actions);
    }
    return card;
  }

  function renderRequests() {
    const container = $("#requestsList");
    container.replaceChildren();
    state.requests.forEach((item) => container.append(renderRequestCard(item)));
    $("#emptyRequests").classList.toggle("hidden", state.requests.length > 0);
    const pending = state.requests.filter((item) => item.status === "pending").length;
    $("#requestNavCount").textContent = state.requests.length;
    $("#approvalNavCount").textContent = pending;
    $("#requestMetrics").innerHTML = [
      ["Solicitudes", state.requests.length],
      ["Pendientes", pending],
      ["Aprobadas", state.requests.filter((item) => item.status === "approved").length],
    ].map(([label, value]) => `<article class="metric-card"><span>${label}</span><strong>${value}</strong></article>`).join("");
  }

  function renderApprovals() {
    const container = $("#approvalsList");
    container.replaceChildren();
    const requests = state.requests.filter((item) =>
      state.approvalFilter === "all" || item.status === state.approvalFilter);
    requests.forEach((item) => container.append(renderRequestCard(item, true)));
    $("#emptyApprovals").classList.toggle("hidden", requests.length > 0);
    const pending = state.requests.filter((item) => item.status === "pending").length;
    $("#approvalSummary").innerHTML = `<div><span>Pendientes de revisión</span><strong>${pending}</strong></div><p>Las solicitudes quedan pendientes hasta su revisión. Aprobarlas no cobra dinero ni confirma un envío.</p>`;
  }

  async function refreshRequests() {
    try {
      const requests = await fetchApi("/api/requests");
      if (!Array.isArray(requests) || !requests.every(isValidRequest)) {
        throw new Error("El servidor devolvió una lista de solicitudes no válida.");
      }
      state.requests = requests;
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        state.requests = readStoredRequests();
      } else if (error.status) {
        console.error("No se pudieron recuperar las solicitudes del servidor.", error);
        showToast(error.message, "error");
      } else {
        console.warn("El servidor no está disponible; se mostrarán las solicitudes locales.", error);
      }
      state.requests = readStoredRequests();
    }
    renderRequests();
    renderApprovals();
  }

  async function loadAdminStatus() {
    try {
      const status = await fetchApi("/api/admin/status");
      state.adminBackendAvailable = true;
      state.adminConfigured = status.configured === true;
      state.adminAuthenticated = status.authenticated === true;
      state.csrfToken = typeof status.csrf_token === "string" ? status.csrf_token : "";
      $("#adminLogout").classList.toggle("hidden", !state.adminAuthenticated);
      if (state.adminAuthenticated) void refreshRequests();
    } catch (error) {
      state.adminBackendAvailable = !error.status;
      console.warn("No se pudo consultar el estado de administración.", error);
    } finally {
      state.adminStatusLoaded = true;
    }
  }

  async function openApprovals() {
    if (!state.adminStatusLoaded) await loadAdminStatus();
    if (state.adminBackendAvailable && !state.adminAuthenticated) {
      $("#adminLoginMessage").textContent = state.adminConfigured
        ? "Inicia sesión para consultar solicitudes y administrar el panel."
        : "El panel está protegido, pero falta configurar NEXUS_ADMIN_PASSWORD en el servidor.";
      $("#adminLoginSubmit").disabled = !state.adminConfigured;
      $("#adminLoginError").classList.add("hidden");
      setOverlay($("#adminLoginOverlay"), true);
      if (state.adminConfigured) $("#adminPassword").focus();
      return;
    }
    await refreshRequests();
    showView("approvals");
  }

  async function submitAdminLogin(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = $("#adminLoginSubmit");
    const errorMessage = $("#adminLoginError");
    submit.disabled = true;
    errorMessage.classList.add("hidden");
    try {
      const password = new FormData(form).get("password");
      const result = await fetchApi("/api/admin/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      state.adminAuthenticated = result.authenticated === true;
      state.csrfToken = result.csrf_token;
      $("#adminLogout").classList.toggle("hidden", !state.adminAuthenticated);
      setOverlay($("#adminLoginOverlay"), false);
      form.reset();
      await refreshRequests();
      showView("approvals");
    } catch (error) {
      errorMessage.textContent = error.message || "No se pudo iniciar sesión.";
      errorMessage.classList.remove("hidden");
    } finally {
      submit.disabled = !state.adminConfigured;
    }
  }

  async function logoutAdmin() {
    try {
      await fetchApi("/api/admin/logout", { method: "POST", body: "{}" });
      state.adminAuthenticated = false;
      state.csrfToken = "";
      state.requests = readStoredRequests();
      $("#adminLogout").classList.add("hidden");
      renderRequests();
      renderApprovals();
      showView("catalog");
      showToast("Sesión administrativa cerrada.");
    } catch (error) {
      showToast(error.message || "No se pudo cerrar la sesión.", "error");
    }
  }

  function showView(view) {
    const names = {
      catalog: "Catálogo",
      requests: "Mis solicitudes",
      approvals: "Centro de aprobaciones",
      about: "Visión y misión",
    };
    Object.entries(names).forEach(([key, label]) => {
      $(`#${key}View`).classList.toggle("hidden", key !== view);
      const navButton = $(`.nav-link[data-view="${key}"]`);
      navButton.classList.toggle("active", key === view);
      navButton.setAttribute("aria-current", key === view ? "page" : "false");
      if (key === view) $("#breadcrumbCurrent").textContent = label;
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setOverlay(overlay, isOpen) {
    overlay.classList.toggle("hidden", !isOpen);
    overlay.setAttribute("aria-hidden", String(!isOpen));
    const hasOpenOverlay = $$(".overlay").some((item) => !item.classList.contains("hidden"));
    document.body.classList.toggle("modal-open", hasOpenOverlay);
    if (isOpen) {
      const focusable = $("button, input, textarea", overlay);
      focusable?.focus();
    }
  }

  async function submitRequest(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const cartItems = Object.entries(state.cart)
      .filter(([id, quantity]) => getProduct(id) && quantity > 0)
      .map(([product_id, quantity]) => ({ product_id, quantity }));
    if (!cartItems.length) {
      showToast("Agrega al menos un producto antes de enviar la solicitud.", "error");
      return;
    }
    const data = new FormData(form);
    const payload = {
      client: String(data.get("client") || "").trim(),
      email: String(data.get("email") || "").trim(),
      note: String(data.get("note") || "").trim(),
      items: cartItems,
    };
    const button = $("#submitRequest");
    button.disabled = true;
    button.textContent = "Enviando solicitud…";
    let savedLocally = false;
    try {
      let created;
      try {
        created = await fetchApi("/api/requests", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } catch (error) {
        if (error.status) throw error;
        const localItems = cartItems.map(({ product_id, quantity }) => {
          const product = getProduct(product_id);
          return {
            product_id,
            name: product.name,
            quantity,
            unit_price: product.price,
          };
        });
        created = {
          ...payload,
          id: crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          items: localItems,
          total: localItems.reduce((sum, item) => sum + item.unit_price * item.quantity, 0),
          status: "pending",
          created_at: new Date().toISOString(),
        };
        state.requests.unshift(created);
        writeStorage(STORAGE.requests, state.requests);
        savedLocally = true;
      }
      if (!state.requests.some((item) => item.id === created.id)) state.requests.unshift(created);
      state.cart = {};
      writeStorage(STORAGE.cart, state.cart);
      renderCart();
      renderRequests();
      renderApprovals();
      form.reset();
      setOverlay($("#requestOverlay"), false);
      setOverlay($("#cartOverlay"), false);
      showView("requests");
      showToast("Tu solicitud quedó registrada para revisión.");
      if (API_BASE && !savedLocally) void refreshRequests();
    } catch (error) {
      showToast(error.message || "No se pudo enviar la solicitud.", "error");
    } finally {
      button.disabled = false;
      button.innerHTML = "Registrar solicitud <span>→</span>";
    }
  }

  async function decideRequest(button) {
    const requestId = button.dataset.requestId;
    const status = button.dataset.decision;
    button.disabled = true;
    try {
      const updated = await fetchApi(`/api/requests/${encodeURIComponent(requestId)}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      state.requests = state.requests.map((item) => item.id === updated.id ? updated : item);
      showToast(status === "approved" ? "Solicitud aprobada." : "Solicitud rechazada.");
    } catch (error) {
      if (error.status) {
        showToast(error.message, "error");
        button.disabled = false;
        return;
      }
      const target = state.requests.find((item) => item.id === requestId);
      if (!target || target.status !== "pending") {
        showToast("La solicitud ya no está pendiente.", "error");
        button.disabled = false;
        return;
      }
      target.status = status;
      target.decided_at = new Date().toISOString();
      writeStorage(STORAGE.requests, state.requests);
      showToast(status === "approved" ? "Solicitud aprobada (demo local)." : "Solicitud rechazada (demo local).");
    }
    renderRequests();
    renderApprovals();
  }

  function addChatMessage(role, text) {
    const message = document.createElement("article");
    message.className = `chat-message ${role === "assistant" ? "assistant-message" : "user-message"}`;
    if (role === "assistant") {
      const avatar = document.createElement("span");
      avatar.className = "chat-avatar";
      avatar.textContent = "N";
      message.append(avatar);
    }
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    message.append(paragraph);
    $("#aiChatMessages").append(message);
    message.scrollIntoView({ block: "nearest", behavior: "smooth" });
    return message;
  }

  function normalizeText(value) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
  }

  function localCatalogAnswer(question) {
    const normalizedQuestion = normalizeText(question);
    if (/\b(hola|buenas|buenos dias|buenas tardes|buenas noches)\b/.test(normalizedQuestion)) {
      return "¡Hola! Soy NEXUS Copilot. Puedo ayudarte a explorar el catálogo, comparar productos y explicar cómo funciona esta demostración.";
    }
    if (/\b(pago|pagar|tarjeta|cobro|comprar|compra real|envio|entrega)\b/.test(normalizedQuestion)) {
      return "NEXUS tiene un checkout integrado únicamente para pagos Sandbox: no cobra dinero real ni genera envíos. La disponibilidad y los precios del catálogo son referenciales y no están confirmados con un proveedor.";
    }
    if (/\b(solicitud|aprobacion|aprobada|pendiente|seguimiento|estado)\b/.test(normalizedQuestion)) {
      return "Puedes revisar tus solicitudes en «Mis solicitudes». Quedan pendientes para revisión desde «Aprobaciones»; aprobar una solicitud no cobra dinero ni confirma una compra o envío.";
    }
    if (
      /\b(cuantos|cuantas|numero de|total de)\b/.test(normalizedQuestion)
      || /\bcatalogo\b/.test(normalizedQuestion) && /\b(hay|tiene|incluye|categorias)\b/.test(normalizedQuestion)
      || /\bcategorias\b/.test(normalizedQuestion)
    ) {
      const categories = new Set(state.products.map((product) => product.category));
      return `El catálogo tiene ${state.products.length} productos en ${categories.size} categorías. Puedes filtrarlos, comparar precios referenciales y agregar opciones al carrito para revisar el checkout Sandbox o registrar una solicitud pendiente.`;
    }
    const categoryTerms = {
      Portátiles: ["portatil", "laptop", "programar", "estudiar", "trabajar", "computador"],
      Celulares: ["celular", "telefono", "movil", "smartphone"],
      Tabletas: ["tableta", "tablet", "ipad"],
      Componentes: ["componente", "tarjeta grafica", "grafica", "gpu", "memoria", "ram", "ssd", "placa", "procesador", "pc", "gaming", "jugar"],
      Periféricos: ["periferico", "monitor", "teclado", "mouse", "audifono", "auriculares"],
      Videojuegos: ["consola", "videojuego", "playstation", "nintendo", "switch"],
      Impresión: ["impresora", "imprimir"],
      Repuestos: ["repuesto", "cargador", "accesorio"],
    };
    const preferredCategory = Object.entries(categoryTerms)
      .map(([category, terms]) => ({
        category,
        score: terms.reduce((score, term) => score + (normalizedQuestion.includes(term) ? 1 : 0), 0),
      }))
      .sort((a, b) => b.score - a.score)[0];
    const budgetMatch = normalizedQuestion.match(/(?:presupuesto|hasta|maximo|maxima|menos de|menos|tope)\D{0,16}(\d[\d.,]*)\s*(millones|millon|m|mil)?/);
    let budget = null;
    if (budgetMatch) {
      const amount = Number(budgetMatch[1].replace(/[.,]/g, ""));
      const unit = budgetMatch[2];
      if (Number.isFinite(amount) && amount > 0) {
        budget = unit === "m" || unit?.startsWith("millon")
          ? amount * 1_000_000
          : unit === "mil"
            ? amount * 1_000
            : amount >= 1000 ? amount : amount * 1_000_000;
      }
    }

    const stopWords = new Set([
      "para", "como", "cual", "cuales", "quiero", "busco", "necesito", "tengo",
      "recomiendas", "recomienda", "mejor", "mejores", "precio", "cuanto", "cuesta",
      "con", "una", "uno", "que", "del", "por", "las", "los", "este", "esta",
      "donde", "puedes", "ayudar", "equipo", "opcion", "opciones", "nexus",
    ]);
    const terms = normalizedQuestion
      .split(/[^a-z0-9]+/)
      .filter((term) => term.length > 2 && !stopWords.has(term));
    const candidates = state.products
      .map((product) => {
        const productText = productSearchText(product);
        const textScore = terms.reduce((score, term) => score + (productText.includes(term) ? 2 : 0), 0);
        const categoryScore = preferredCategory?.score
          ? product.category === preferredCategory.category ? 5 : -1
          : 0;
        const budgetScore = budget
          ? product.price <= budget ? 2 + product.price / budget : -4
          : 0;
        return { product, score: textScore + categoryScore + budgetScore };
      })
      .filter(({ product }) => !budget || product.price <= budget)
      .sort((a, b) => b.score - a.score || a.product.price - b.product.price);

    const bestScore = candidates[0]?.score ?? 0;
    if (bestScore <= 0 && !preferredCategory?.score && !budget) {
      return "En el modo local puedo responder sobre el catálogo y el proceso de demostración. Para preguntas generales, configura Gemini en el servidor; no inventaré una respuesta sin esa conexión.";
    }
    const picks = candidates
      .filter((candidate) => candidate.score >= Math.max(0, bestScore - 2))
      .slice(0, 3)
      .map(({ product }) => product);

    if (!picks.length) {
      return budget
        ? `No encontré productos del catálogo dentro de tu presupuesto de ${money.format(budget)}. Puedes subir el presupuesto o explorar otras categorías.`
        : "No encontré una coincidencia clara con esa pregunta. Prueba mencionando una categoría, por ejemplo: portátil, celular, gaming o monitor.";
    }

    const comparisons = picks.map((product) =>
      `• ${product.name} (${product.category}): ${money.format(product.price)}.`
    ).join("\n");
    const intro = preferredCategory?.score
      ? `Según tu interés en ${preferredCategory.category.toLocaleLowerCase("es")}, estas opciones del catálogo podrían servirte:`
      : "Estas opciones destacadas del catálogo podrían servirte:";
    const guidance = normalizedQuestion.includes("gaming") || normalizedQuestion.includes("jugar")
      ? "\n\nPara gaming, compara el tipo de equipo que ya tienes antes de elegir componentes; verifica la compatibilidad exacta del modelo."
      : normalizedQuestion.includes("estudi") || normalizedQuestion.includes("program")
        ? "\n\nPara estudiar o programar, valora también memoria, almacenamiento y portabilidad según los programas que uses."
        : "";
    return `${intro}\n${comparisons}${guidance}\n\nOrientación local basada en el catálogo de NEXUS. Precios, especificaciones y disponibilidad son referenciales; no hay ventas reales habilitadas.`;
  }

  async function loadAiStatus() {
    const badge = $("#aiStatusBadge");
    const notice = $("#aiChatNotice");
    try {
      const status = await fetchApi("/api/ai/status");
      state.aiConfigured = status.configured;
      state.aiStatusLoaded = true;
      badge.innerHTML = status.configured
        ? "<i></i> Gemini conectado"
        : "<i></i> Copilot catálogo";
      badge.classList.toggle("ai-connected", status.configured);
      notice.textContent = status.configured
        ? `Asistente generativo conectado a ${status.provider} · ${status.model}. Evita compartir datos personales.`
        : "Modo local: respondo sobre el catálogo y el proceso de demostración. Para preguntas generales, configura Gemini en el servidor.";
    } catch (error) {
      console.warn("No se pudo consultar el estado del asistente.", error);
      state.aiStatusLoaded = true;
      badge.textContent = "Asistente sin conexión";
      notice.textContent = "Modo local: respondo sobre el catálogo y el proceso de demostración. Si el servidor de IA no está disponible, no puedo responder preguntas generales.";
    }
  }

  async function submitChat(event) {
    event.preventDefault();
    if (state.sending) return;
    const input = $("#aiChatInput");
    const question = input.value.trim();
    if (!question) return;
    if (!state.aiStatusLoaded) await loadAiStatus();
    const history = $$(".chat-message", $("#aiChatMessages"))
      .map((message) => ({
        role: message.classList.contains("user-message") ? "user" : "assistant",
        content: $("p", message).textContent,
      }))
      .filter((message) => message.content)
      .slice(-6);
    while (history[0]?.role === "assistant") history.shift();
    history.push({ role: "user", content: question });
    addChatMessage("user", question);
    input.value = "";
    const send = $("#aiChatSend");
    state.sending = true;
    send.disabled = true;
    send.textContent = "Pensando…";
    const waiting = addChatMessage("assistant", "Estoy revisando el catálogo…");
    waiting.classList.add("chat-pending");
    try {
      const result = state.aiConfigured
        ? await fetchApi("/api/ai/chat", {
          method: "POST",
          body: JSON.stringify({ messages: history }),
        })
        : await Promise.resolve({ answer: localCatalogAnswer(question) });
      waiting.remove();
      addChatMessage("assistant", result.answer);
    } catch (error) {
      waiting.remove();
      addChatMessage("assistant", error.message || "No fue posible responder. Inténtalo de nuevo.");
    } finally {
      state.sending = false;
      send.disabled = false;
      send.innerHTML = "Enviar <span>↑</span>";
      input.focus();
    }
  }

  async function initialize() {
    try {
      state.products = await fetchApi("/api/products");
      $("#connectionPill").innerHTML = "<i></i> Backend Python";
      $("#connectionPill").classList.add("is-connected");
    } catch (error) {
      console.info("El backend no está disponible; se intentará usar el catálogo local.", error);
      try {
        const response = await fetch("./static/products.json");
        if (!response.ok) throw new Error(`Catálogo local: HTTP ${response.status}`);
        state.products = await response.json();
        $("#connectionPill").innerHTML = "<i></i> Demo local";
      } catch (catalogError) {
        console.error("No se pudo cargar el catálogo.", catalogError);
        $("#connectionPill").textContent = "Catálogo no disponible";
        showToast("No se pudo cargar el catálogo. Abre la página desde Flask o Live Server.", "error");
      }
    }
    if (!Array.isArray(state.products)) {
      state.products = [];
      showToast("El catálogo recibido tiene un formato inválido.", "error");
    }
    renderProducts();
    renderCart();
    renderRecommendation();
    state.requests = readStoredRequests();
    renderRequests();
    renderApprovals();
    void loadAiStatus();
    void loadAdminStatus();
    void loadStoreStatus();
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const nav = target.closest("[data-view]");
    if (nav) {
      if (nav.dataset.view === "approvals") {
        void openApprovals();
        return;
      }
      showView(nav.dataset.view);
      return;
    }
    const detail = target.closest("[data-product-details]");
    if (detail) {
      renderProductDetails(detail.dataset.productDetails);
      return;
    }
    const add = target.closest("[data-add-product]");
    if (add) {
      addToCart(add.dataset.addProduct);
      return;
    }
    const quantity = target.closest("[data-quantity]");
    if (quantity) {
      adjustQuantity(quantity.parentElement.dataset.productId, Number(quantity.dataset.quantity));
      return;
    }
    const decision = target.closest("[data-decision]");
    if (decision) {
      void decideRequest(decision);
      return;
    }
    const category = target.closest("[data-category]");
    if (category) {
      state.category = category.dataset.category;
      if (state.category !== "Todos") {
        state.interests[state.category] = (state.interests[state.category] || 0) + 1;
        writeStorage(STORAGE.interests, state.interests);
        renderRecommendation();
      }
      $$(".category-tab").forEach((tab) => tab.classList.toggle("selected", tab === category));
      renderProducts();
      return;
    }
    const filter = target.closest("[data-status]");
    if (filter) {
      state.approvalFilter = filter.dataset.status;
      $$("#approvalFilters .filter-chip").forEach((chip) => chip.classList.toggle("active", chip === filter));
      renderApprovals();
      return;
    }
    const prompt = target.closest("[data-prompt]");
    if (prompt) {
      $("#aiChatInput").value = prompt.dataset.prompt;
      $("#aiChatInput").focus();
      return;
    }
    if (target.closest("[data-close-cart]")) setOverlay($("#cartOverlay"), false);
    if (target.closest("[data-close-store]")) {
      void closeStoreCheckout();
      return;
    }
    if (target.closest("[data-close-request]")) setOverlay($("#requestOverlay"), false);
    if (target.closest("[data-close-ai-chat]")) setOverlay($("#aiChatOverlay"), false);
    if (target.closest("[data-close-details]")) setOverlay($("#productDetailsOverlay"), false);
    if (target.closest("[data-close-admin-login]")) setOverlay($("#adminLoginOverlay"), false);
    if (target.closest("#adminLogout")) {
      void logoutAdmin();
      return;
    }
    if (target.closest("#cartButton")) {
      setOverlay($("#cartOverlay"), true);
      return;
    }
    if (target.closest("#confirmContinue")) {
      void closeStoreCheckout();
      showView("catalog");
      return;
    }
    if (target.closest("#confirmViewRequests")) {
      void closeStoreCheckout();
      showView("requests");
      return;
    }
    if (target.closest("#checkoutButton")) {
      setOverlay($("#cartOverlay"), false);
      const total = Object.entries(state.cart).reduce((sum, [id, quantity]) => {
        const product = getProduct(id);
        return sum + (product ? product.price * quantity : 0);
      }, 0);
      $("#storeOrderTotal").textContent = money.format(total);
      state.simulatedOrder = null;
      if (state.storeStatusLoaded) {
        renderStoreReadiness({ configured: state.storePaymentReady, public_key: state.storePublicKey, live_sales_enabled: false });
      }
      setOverlay($("#storeCheckoutOverlay"), true);
      $("#storeCheckoutOverlay .modal-card").scrollTop = 0;
      void loadStoreStatus();
      if (state.checkoutOrder) void renderCardPaymentBrick();
      return;
    }
    if (target.closest("#restartStoreCheckout")) {
      void restartStoreCheckout();
      return;
    }
    if (target.closest("#aiChatOpen")) {
      setOverlay($("#aiChatOverlay"), true);
      return;
    }
    if (target.closest("#exploreButton, #showAllButton, [data-go-catalog]")) {
      showView("catalog");
      $("#catalog").scrollIntoView({ behavior: "smooth" });
      return;
    }
    if (target.classList.contains("overlay")) {
      if (target.id === "storeCheckoutOverlay") void closeStoreCheckout();
      else setOverlay(target, false);
    }
  });

  $("#searchInput").addEventListener("input", (event) => {
    state.search = normalizeText(event.target.value.trim());
    renderProducts();
  });
  $("#sortSelect").addEventListener("change", (event) => {
    state.sort = event.target.value;
    renderProducts();
  });
  $("#requestForm").addEventListener("submit", (event) => void submitRequest(event));
  $("#storeOrderForm").addEventListener("submit", (event) => void submitStoreOrder(event));
  $("#adminLoginForm").addEventListener("submit", (event) => void submitAdminLogin(event));
  $("#aiChatForm").addEventListener("submit", (event) => void submitChat(event));
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!$("#storeCheckoutOverlay").classList.contains("hidden")) void closeStoreCheckout();
    [$("#cartOverlay"), $("#requestOverlay"), $("#aiChatOverlay"), $("#productDetailsOverlay"), $("#adminLoginOverlay")].forEach((overlay) => {
      if (!overlay.classList.contains("hidden")) setOverlay(overlay, false);
    });
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("#searchInput").focus();
    }
  });

  void initialize();
})();
