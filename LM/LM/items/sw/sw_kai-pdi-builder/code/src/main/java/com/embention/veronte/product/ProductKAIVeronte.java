package com.embention.veronte.product;

import com.embention.core.guifx.product.IProduct;
import com.embention.core.guifx.product.data.XpcU8ConsumerParams;
import com.embention.core.guifx.product.data.XpcU8ProducerParams;
import com.embention.core.guifx.setup.xpc.XPCPanel;
import com.embention.setup.veronte.communication.ports.PortsIds1x;
import com.embention.veronte.data.*;
import com.embention.veronte.data.FMsg.FMCPmgrType;
import com.embention.veronte.data.FMsgSet.Array_cons;
import com.embention.veronte.data.XPC.Consumer;
import com.embention.veronte.data.boards.ProductPortRegistry;
import com.embention.veronte.data.boards.XpcMgr;
import com.embention.veronte.data.boards.XpcMgr.XPCType;
import com.embention.veronte.data.configuration.VConfig;

import java.util.*;

public class ProductKAIVeronte implements IProduct {

    List<ConfigId> consumers = Arrays.asList(
            ConfigId.CFG_FMSG_C,
            ConfigId.CFG_FMSG_P,
            ConfigId.CFG_CANTM_P0,
            ConfigId.CFG_CANTM_C0,
            ConfigId.CFG_CANTM_P1,
            ConfigId.CFG_CANTM_C1,
            ConfigId.CFG_CANTM_P2,
            ConfigId.CFG_CANTM_C2
    );

    @Override
    public List<ConfigId> getCANConsumerConfig() {
        return consumers;
    }

    @Override
    public List<ConfigId> getSerialConsumerConfig() {
        return consumers;
    }

    @Override
    public boolean hasMailBoxes() {
        return true;
    }

    @Override
    public boolean showUVar() {
        return true;
    }

    @Override
    public boolean showRVar() {
        return true;
    }

    @Override
    public boolean showBit() {
        return true;
    }

    @Override
    public boolean showR64Var() { return true; }

  @Override
  public <T> boolean isExternalSensor(VConfig config, Consumer<T> consumer) {
      if(consumer.getType() != XPCCanType.CUSTOM){
        return false;
      }
      int fmgIdOffset = XpcMgr.createProvider(XPCType.can, config.getAppId(), config.getHwRev())
          .getConsumersByType(XPCCanType.CUSTOM).getFirst().getId();
      FMsgSet fmsgList = ((Array_cons)config.getItunable(ConfigId.CFG_FMSG_C)).get(consumer.getId() - fmgIdOffset);
      boolean isExternalSensor = fmsgList.size() > 0;
      for(int i = 0; i < fmsgList.size(); ++i) {
        if(fmsgList.get(i).getFmcPmgrType() != FMCPmgrType.tExtSens) {
          isExternalSensor = false;
        }
      }
      return  !isExternalSensor;
  }

  @Override
    public XPCPanel<XPCCanType> buildCanPanel(String name, VConfig config) {
        XpcCanTraitContainer xpccantraitVer = config.getItunable(ConfigId.CFG_XPCCAN);
        List<Fcanconsumer> fcanconsumers = List.of(config.getItunable(ConfigId.CFG_CANTM_C0), config.getItunable(ConfigId.CFG_CANTM_C1), config.getItunable(ConfigId.CFG_CANTM_C2));
        List<Fcanproducer> fcanproducers = List.of(config.getItunable(ConfigId.CFG_CANTM_P0), config.getItunable(ConfigId.CFG_CANTM_P1), config.getItunable(ConfigId.CFG_CANTM_P2));
        Fmset fmset = config.getItunable(ConfigId.CFG_FMSET);

      SerialCan canSuite_sc = config.getItunable(ConfigId.CFG_CANSUITE_SC);
      CanInFilt caninFilt = config.getItunable(ConfigId.CFG_CANSUITE_IN);
      CanSuiteVeronte canSuite = config.getItunable(ConfigId.CFG_CANSUITE_GPIO);

        CanOutFilt canOutFilt = config.getItunable(ConfigId.CFG_CANSUITE_OUT);
    ProductPortRegistry<XPCCanType> xpcProvider = XpcMgr.createProvider(XPCType.can, config.getAppId(), config.getHwRev());
        return new XPCPanel<>(name,
            xpccantraitVer.getXpc(),
            IProduct.getCanConsumerMapPanel(xpcProvider, this, config, canOutFilt),
            IProduct.getCanProducerMapPanel(xpcProvider, canSuite_sc, caninFilt, canSuite),
            config,
            this,
            XpcMgr.XPCType.can,
            fcanconsumers,
            fcanproducers,
            fmset,
            Set.of(ConfigId.CFG_XPCCAN,
                ConfigId.CFG_CANTM_C0, ConfigId.CFG_CANTM_C1, ConfigId.CFG_CANTM_C2,
                ConfigId.CFG_CANTM_P0, ConfigId.CFG_CANTM_P1, ConfigId.CFG_CANTM_P2,
                ConfigId.CFG_FMSET, ConfigId.CFG_CAN_TERMS, ConfigId.CFG_CANSUITE_GPIO,
                ConfigId.CFG_CANSUITE_SC, ConfigId.CFG_CANSUITE_IN, ConfigId.CFG_CANSUITE_OUT));
    }

    @Override
    public XPCPanel<XpcU8Type> buildXpcU8Panel(String name, VConfig config) {
        Set<ConfigId> configids = new HashSet<>();
        Tunnel.Array tunnelOut = config.getItunable(ConfigId.CFG_TUNNEL8C);

        configids.addAll(getSerialConsumerConfig());
        configids.addAll(Set.of(ConfigId.CFG_XPCU8, ConfigId.CFG_TUNNEL8C, ConfigId.CFG_PORTS,
            ConfigId.CFG_FMSG_C, ConfigId.CFG_FMSG_P, ConfigId.CFG_UNESCAPE));
      ProductPortRegistry<XpcU8Type> xpcProvider = XpcMgr.createProvider(XPCType.xpcu8, config.getAppId(), config.getHwRev());
        return new XPCPanel<>(
            name,
            ((Xpcu8traitContainer) config.getItunable(ConfigId.CFG_XPCU8)).getXpc(),
            IProduct.getXpcU8ConsumerMapPanel( this, XpcU8ConsumerParams.builder(xpcProvider,config)
                    .tunnelOut(tunnelOut)
                    .fmSet(config.getItunable(ConfigId.CFG_FMSET))
                    .fMsgArray(config.getItunable(ConfigId.CFG_FMSG_C))
                    .unescape(config.getItunable(ConfigId.CFG_UNESCAPE)).build()
            ),
            IProduct.getXpcU8ProducerMapPanel(this, XpcU8ProducerParams.builder(xpcProvider, config)
                    .commConfig(config.getItunable(ConfigId.CFG_PORTS))
                    .fmSet(config.getItunable(ConfigId.CFG_FMSET))
                    .fMsgArray(config.getItunable(ConfigId.CFG_FMSG_P)).build()),
            config,
            this,
            XpcMgr.XPCType.xpcu8,
            configids);
    }

    @Override
    public XPCPanel<XpcCap.Type> buildEcap(String name, VConfig config) {
      ProductPortRegistry<XpcCap.Type> xpcProvider = XpcMgr.createProvider(XPCType.ecap, config.getAppId(), config.getHwRev());
        return new XPCPanel<>(name,
            ((XpcEcapTraitContainer) config.getItunable(ConfigId.CFG_XPECAP)).getXpc(),
            IProduct.getEcapConsumerMapPanel(xpcProvider,
                config.getItunable(ConfigId.CFG_CAPPULSE)),
            IProduct.getEcapProducerMapPanel(xpcProvider, config,
                config.getItunable(ConfigId.CFG_ECAP)),
            config,
            this,
            XpcMgr.XPCType.ecap,
            Set.of(ConfigId.CFG_ECAP, ConfigId.CFG_CAPPULSE));
    }

    @Override
    public boolean isEditableVarName() {
        return true;
    }

    @Override
    public List<RVarId> getRVarIdList() {
        return new ArrayList<>(RVarId.getAllUsed());
    }

    @Override
    public List<UVarId> getUVarIdList() {
        return new ArrayList<>(UVarId.getAllUsed());
    }

    @Override
    public List<Bit> getUBitIdList() {
        return new ArrayList<>(Bit.getAllUsed());
    }

    @Override
    public List<R64VarId> getR64VarIdList() { return new ArrayList<>(R64VarId.getAllUsed()); }


    @Override
    public int getMaxRoutingTables() {
        return 2;
    }

    @Override
    public int getMaxEntities() {
        return 16;
    }
    @Override
    public Enum[] getPortsValues() {
        return PortsIds1x.values();
    }
}
