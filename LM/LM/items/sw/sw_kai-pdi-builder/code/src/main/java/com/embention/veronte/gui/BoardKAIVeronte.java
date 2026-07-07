package com.embention.veronte.gui;

import com.embention.blocks.blocksgui.default_blocks.BlocksDefault;
import com.embention.blocks.blocksgui.devices.DynamicPressureDevicePanelController;
import com.embention.blocks.blocksgui.devices.StaticPressurePanel;
import com.embention.common.com.event.dto.devices.DeviceDTO;
import com.embention.common.core.*;
import com.embention.common.core.AppVersion.AppId;
import com.embention.common.core.hw.HWRevision;
import com.embention.common.core.hw.HWRevision1x;
import com.embention.common.core.hw.HWRevisionKAI;
import com.embention.guifx.log.LogType;
import com.embention.setup.veronte.communication.ethernet.EthernetPanelController;
import com.embention.setup.veronte.control.ControlPanelController.ControlPanelData;
import com.embention.veronte.data.Field;
import com.embention.veronte.data.boards.kai.Xpcu8traitVerKAI;
import com.embention.veronte.data.tm.Fieldset;
import com.embention.core.guifx.ItunablePane;
import com.embention.core.guifx.board.Board;
import com.embention.core.guifx.board.IncrementalCounterPanelController;
import com.embention.core.guifx.board.TabSciPanelController;
import com.embention.core.guifx.board.canfd.CanFdPanelController;
import com.embention.core.guifx.board.category.MenuCategory;
import com.embention.core.guifx.panel.StatusPanelController;
import com.embention.core.guifx.product.IProduct;
import com.embention.guifx.IConfigPane;
import com.embention.guifx.IConfigPaneAdder;
import com.embention.setup.veronte.ProductVersionSingleton;
import com.embention.setup.veronte.automations.AutomationPanelController;
import com.embention.setup.veronte.blocks.BlockProgramSummary;
import com.embention.setup.veronte.communication.iridium.IridiumPanelController;
import com.embention.setup.veronte.communication.ports.PortsPanel;
import com.embention.setup.veronte.communication.sara.SaraPanel;
import com.embention.setup.veronte.communication.stats.ComstatsPanel;
import com.embention.setup.veronte.control.ControlPanelController;
import com.embention.setup.veronte.hilmapping.HILMappingPanelController;
import com.embention.setup.veronte.safety.bits.SafetyBitsPanelController;
import com.embention.setup.veronte.safety.checklist.CheckListPanelController;
import com.embention.setup.veronte.safety.pdifs.ConfigManagerPanelController;
import com.embention.setup.veronte.sensors.*;
import com.embention.setup.veronte.stanag.StanagVariablesController;
import com.embention.setup.veronte.telemetry.FieldPanelController;
import com.embention.setup.veronte.ui.variables.OperationVariableRenameController;
import com.embention.setup.veronte.ui.variables.VariableNameController;
import com.embention.setup.veronte.unit.attitude.VisualVeronte;
import com.embention.setup.veronte.unit.freqmgr.FreqMgr;
import com.embention.setup.veronte.unit.name.IPVeronteController;
import com.embention.veronte.data.*;
import com.embention.veronte.data.Telemetry.Data;
import com.embention.veronte.data.Telemetry.TMEntry;
import com.embention.veronte.data.configuration.VConfig;
import com.embention.veronte.pdigen.vxml.XSCfg.XsRootCfg;
import com.embention.veronte.product.ProductKAIVeronte;
import com.embention.veronte.types.RmatrixPk0;

import java.util.*;
import util.ubx.UbxConfig;

public class BoardKAIVeronte extends Board {
  private final BlocksDefault blocksDefault = new BlocksDefault();

  public BoardKAIVeronte() {
    super(XsRootCfg.VER);
  }

  @Override
  public List<AppId> getProductAppId() {
    return List.of(AppVersion.AppId.kai);
  }

  public String getNameBoard() {
    return "KAI";
  }

  @Override
  public Map<MenuCategory, IConfigPane> buildPanels() {
    IProduct product = new ProductKAIVeronte();
    TreeMap<MenuCategory, IConfigPane> panels = new TreeMap<>();
    VConfig cfg = getConfig();
    IConfigPaneAdder pane;

    panels.put(MenuCategory.VERONTE, MenuCategory.VERONTE.build(cfg));
    pane = (IConfigPaneAdder) panels.get(MenuCategory.VERONTE);
    pane.addPanel(new IPVeronteController(cfg));
    pane.addPanel(new VisualVeronte(cfg));
    pane.addPanel(new FreqMgr(cfg.getItunable(ConfigId.CFG_FREQMGR)));
//    pane.addPanel(new GPIOpanelController(cfg.getItunable(ConfigId.CFG_GPIO)));
    pane.addPanel(new StatusPanelController(cfg));

//    panels.put(MenuCategory.CONNECTIONS,new V4ConnectionPanel(cfg));

    panels.put(MenuCategory.SENSORS, MenuCategory.SENSORS.build(cfg));
    pane = (IConfigPaneAdder) panels.get(MenuCategory.SENSORS);
    pane.addPanel(new SensorFusionController(cfg, ConfigId.CFG_ACCLPS, ConfigId.CFG_ACCINI, ConfigId.CFG_VARACC, ConfigId.CFG_EXT_ACC0, ConfigId.CFG_EXT_ACC1,"Accelerometer"));
    pane.addPanel(new SensorFusionController(cfg, ConfigId.CFG_GYRLPS, ConfigId.CFG_GYRINI, ConfigId.CFG_VARGYR, ConfigId.CFG_EXT_GYR0, ConfigId.CFG_EXT_GYR1, "Gyroscope"));
    pane.addPanel(new Suite3DPanel(new ASuite.SensorIndex(), ConfigId.CFG_MAGLPS, cfg, ConfigId.CFG_VARMAG, ConfigId.CFG_EXT_MAG0, ConfigId.CFG_EXT_MAG1, "Magnetometer"));
    pane.addPanel(new DynamicPressureDevicePanelController(cfg));
    pane.addPanel(new StaticPressurePanel(cfg));
//    AnyTabPaneController rpmPanel = new AnyTabPaneController(cfg, "RPM", Set.of(ConfigId.CFG_RPM.getId()));
//    CapPPS.Array rpm = cfg.getItunable(ConfigId.CFG_RPM);
//    int idx = 0;
//    for (CapPPS stickPpm : rpm.getIterable()) {
//      rpmPanel.put(new CapPPSpanel(stickPpm, "RPM " + idx));
//      idx++;
//    }
//    pane.addPanel(rpmPanel);
//    pane.addPanel(new DevicesI2CPanelController(cfg));
    pane.addPanel(new ExternalNavigationController(cfg));

    panels.put(MenuCategory.IO, MenuCategory.IO.build(cfg));
    pane = (IConfigPaneAdder) panels.get(MenuCategory.IO);
    pane.addPanel(product.buildXpcU8Panel("I/O Comms", cfg));
    pane.addPanel(product.buildCanPanel("CAN Comms", cfg));
    pane.addPanel(new CanFdPanelController(cfg.getItunable(ConfigId.CFG_CAN_FD_A)));
//    pane.addPanel(product.buildEcap("Digital Input", cfg));
    HWRevision hw = ProductVersionSingleton.getInstance().getHwType();

    pane.addPanel(new TabSciPanelController(cfg, false));

    pane.addPanel(new IncrementalCounterPanelController(cfg));

    panels.put(MenuCategory.CONTROL, new ControlPanelController(cfg,
        new ControlPanelData(true, true, true, false)));

    panels.put(MenuCategory.AUTOMATIONS, MenuCategory.AUTOMATIONS.build(cfg));
    pane =(IConfigPaneAdder) panels.get(MenuCategory.AUTOMATIONS);
    pane.addPanel(new AutomationPanelController(cfg));

    panels.put(MenuCategory.COMMUNICATION, MenuCategory.COMMUNICATION.build(cfg));
    pane =(IConfigPaneAdder) panels.get(MenuCategory.COMMUNICATION);
    pane.addPanel(new PortsPanel(cfg, product));
    pane.addPanel(new SaraPanel(cfg.getItunable(ConfigId.CFG_SARA)));
    pane.addPanel(new ComstatsPanel(cfg.getItunable(ConfigId.CFG_COMSTATS)));
    pane.addPanel(new IridiumPanelController(cfg.getItunable(ConfigId.CFG_IRIDIUM)));
    pane.addPanel(new EthernetPanelController(cfg.getItunable(ConfigId.CFG_NETWORK_CONFIG)));
    //pane.addPanel(new RadioPanel(cfg.getItunable(ConfigId.CFG_AMZ_RADIO_ST)));

//    panels.put(MenuCategory.STICK, MenuCategory.STICK.build(cfg));
//    pane =(IConfigPaneAdder) panels.get(MenuCategory.STICK);
//    pane.addPanel(new StickPPMPanel(cfg, ConfigId.CFG_PPM0, "Transmitter 0"));
//    pane.addPanel(new StickPPMPanel(cfg, ConfigId.CFG_PPM1, "Transmitter 1"));
//    pane.addPanel(new StickPPMPanel(cfg, ConfigId.CFG_PPM2, "Transmitter 2"));
//    pane.addPanel(new StickPPMPanel(cfg, ConfigId.CFG_PPM3, "Transmitter 3"));
//    pane.addPanel(new VirtualStickDevicePanelController(cfg));

    panels.put(MenuCategory.BLOCKS, MenuCategory.BLOCKS.build(cfg));
    pane =(IConfigPaneAdder) panels.get(MenuCategory.BLOCKS);
    pane.addPanel(new BlockProgramSummary(cfg, blocksDefault));

    panels.put(MenuCategory.TELEMETRY, MenuCategory.TELEMETRY.build(cfg));
    pane =(IConfigPaneAdder) panels.get(MenuCategory.TELEMETRY);
    pane.addPanel(new FieldPanelController(cfg, product));

    panels.put(MenuCategory.UI, MenuCategory.UI.build(cfg));
    pane =(IConfigPaneAdder) panels.get(MenuCategory.UI);
    pane.addPanel(new OperationVariableRenameController(cfg));
    pane.addPanel(new VariableNameController(cfg));

    panels.put(MenuCategory.HIL, MenuCategory.HIL.build(cfg));
    pane =(IConfigPaneAdder) panels.get(MenuCategory.HIL);
    pane.addPanel(new HILMappingPanelController(cfg));

    panels.put(MenuCategory.SAFETY, MenuCategory.SAFETY.build(cfg));
    pane = (IConfigPaneAdder) panels.get(MenuCategory.SAFETY);
    pane.addPanel(new CheckListPanelController(cfg));
    pane.addPanel(new ConfigManagerPanelController(cfg));
    pane.addPanel(new SafetyBitsPanelController(cfg));

    panels.put(MenuCategory.STANAG, MenuCategory.STANAG.build(cfg));
    pane = (IConfigPaneAdder) panels.get(MenuCategory.STANAG);
    pane.addPanel(new StanagVariablesController(cfg));

    ((Sara) cfg.getItunable(ConfigId.CFG_SARA)).setIs_sara_r5();

    return panels;
  }

  @Override
  public List<ItunablePane> buildCalibrationPanels(DeviceDTO device) {
    return null;
  }

  @Override
  public void setCfgDefaults(VConfig config) {

    HWRevision address = ProductVersionSingleton.getInstance().getDevId().getHwrevision();

    // Default telemetry
    Telemetry tm = new Telemetry();
    Fieldset fs = new Fieldset();
    for (RVarId sv : RVarId.getRequiredByApps()) {
      if (LogType.VOPS.getUnavailable().contains(sv)) {
        continue;
      }
      fs.add(new Field(sv.getSystemVar()));
    }
    for (UVarId sv : UVarId.getRequiredByApps()) {
      fs.add(new Field(sv.getSystemVar()));
    }
    for (Bit sv : Bit.getRequiredByApps()) {
      fs.add(new Field(sv.getSystemVar()));
    }
    tm.add(new TMEntry(fs, new Data(Bit.KBIT_OK, new Address(Address.APP), 0.1f)));
    config.setItunable(ConfigId.CFG_TELEMETRY, tm);

    Fstrt onboardLog = new Fstrt();
    onboardLog.add(new Field(RVarId.tk.getSystemVar()));
    config.setItunable(ConfigId.CFG_FSTR, onboardLog);

    // Default communication port routing
    RoutingTable rtable = new RoutingTable();
    config.setItunable(ConfigId.CFG_ROUTING_TABLE, rtable);

    // Default Xpcu8 connections
    // TODO to be defined according to the HW revision
//    config.setItunable(ConfigId.CFG_XPCU8, Xpcu8traitVer.genSafe(address));

        // Default Xpccan connections
    // TODO to be defined according to the HW revision
//    config.setItunable(ConfigId.CFG_XPCCAN, XpccantraitVer.genSafe());

    // Default CAN Out Filter
    config.setItunable(ConfigId.CFG_CANSUITE_OUT, CanOutFilt.get_default(XpccantraitVer.nb_can_out));

    // Default CAN In Filter
    config.setItunable(ConfigId.CFG_CANSUITE_IN, CanInFilt.get_default(XpccantraitVer.nb_can_in, false, true));

    // Default Serial CAN
    config.setItunable(ConfigId.CFG_CANSUITE_SC, SerialCan.get_default(XpccantraitVer.nb_ser_can, true));

    // Default GPIO for cansuite
    config.setItunable(ConfigId.CFG_CANSUITE_GPIO, CanGPIO_p.get_default(XpccantraitVer.nb_gpio_p));

    config.setItunable(ConfigId.CFG_ACCINI, SuiteFusion.get_default(address));
    config.setItunable(ConfigId.CFG_GYRINI, SuiteFusion.get_default(address));

    Rains rains = Rains.genDefaultQuad();
    config.setItunable(ConfigId.CFG_RAINS, rains);

    config.setItunable(ConfigId.CFG_STP0, DevCommonCfg.genDefStp(ConfigId.CFG_STP0));
    config.setItunable(ConfigId.CFG_STP1, DevCommonCfg.genDefStp(ConfigId.CFG_STP1));
    config.setItunable(ConfigId.CFG_STP2, DevCommonCfg.genDefStp(ConfigId.CFG_STP2));
    config.setItunable(ConfigId.CFG_QINF_FILT, DevCommonCfg.genDefStp(ConfigId.CFG_QINF_FILT));

    config.setItunable(ConfigId.CFG_PORTS, Stanag_ports.get_def(Xpcu8traitVerKAI.XP.com5.getId() - Xpcu8traitVerKAI.XP.com0.getId() + 1));

    RmatrixPk0 initialRaisCovar = RmatrixPk0.genDefault();
    config.setItunable(ConfigId.CFG_PK0, initialRaisCovar);

    UbxConfig ubxConfig0 = config.getItunable(ConfigId.CFG_UBX0);
    UbxConfig ubxConfig1 = config.getItunable(ConfigId.CFG_UBX1);
    ubxConfig0.applyDefaultConfig();
    ubxConfig1.applyDefaultConfig();
  }

  public String getRepositoryKey() {
    return "KAI";
  }

  @Override
  public List<HWRevision> getOptions() {
    return List.of(HWRevisionKAI.hw_lm_1_0);
  }

  @Override
  public void setDefaultOption() {
    selectedAppId = AppId.kai;
    selected = HWRevisionKAI.hw_lm_1_0; //latest version
  }

  @Override
  public double getPrefWidth() {
    return 1020d;
  }
}
