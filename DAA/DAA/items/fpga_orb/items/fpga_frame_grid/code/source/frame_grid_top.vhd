library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity frame_grid_top is
	generic (
		-- Users to add parameters here

		-- User parameters ends
		-- Do not modify the parameters beyond this line

		-- Width of S_AXIS address bus. The slave accepts the read and write addresses of width C_M_AXIS_DATA_WIDTH.
		C_M_AXIS_DATA_WIDTH	: integer	:= 128;
		
		C_M_AXIS_DATA_IDX_WIDTH	: integer	:= 32;
		-- Start count is the number of clock cycles the master will wait before initiating/issuing any transaction.
		C_M_AXIS_START_COUNT	: integer	:= 0;
		
    
		C_S_AXI_DATA_WIDTH	: integer	:= 32;
		
		C_S_AXI_ADDR_WIDTH	: integer	:= 4
	);
	port (
	
		-- Global ports
		ACLK	: in std_logic;
		-- 
		ARESETN	: in std_logic;
		  
		-- BRAM PORT
		addr : out std_logic_vector(31 downto 0);
		clko : out std_logic;
		data : in std_logic_vector(127 downto 0);
		eno : out std_logic;
		rsto : out std_logic;
		
		-- Master Stream Ports. TVALID indicates that the master is driving a valid transfer, A transfer takes place when both TVALID and TREADY are asserted. 
		M_AXIS_TVALID	: out std_logic;
		-- TDATA is the primary payload that is used to provide the data that is passing across the interface from the master.
		M_AXIS_TDATA	: out std_logic_vector(C_M_AXIS_DATA_WIDTH-1 downto 0);
		-- TSTRB is the byte qualifier that indicates whether the content of the associated byte of TDATA is processed as a data byte or a position byte.
		M_AXIS_TSTRB	: out std_logic_vector((C_M_AXIS_DATA_WIDTH/8)-1 downto 0);
		-- TLAST indicates the boundary of a packet.
		M_AXIS_TLAST	: out std_logic;
		-- TREADY indicates that the slave can accept a transfer in the current cycle.
		M_AXIS_TREADY	: in std_logic;
		
		-- Users to add ports here
        reg0 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
        reg1 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
        reg2 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
        reg3 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
		S_AXI_ACLK	: in std_logic;
		S_AXI_ARESETN	: in std_logic;
		S_AXI_AWADDR	: in std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0);
		S_AXI_AWPROT	: in std_logic_vector(2 downto 0);
		S_AXI_AWVALID	: in std_logic;
		S_AXI_AWREADY	: out std_logic;
		S_AXI_WDATA	: in std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
		S_AXI_WSTRB	: in std_logic_vector((C_S_AXI_DATA_WIDTH/8)-1 downto 0);
		S_AXI_WVALID	: in std_logic;
		S_AXI_WREADY	: out std_logic;
		S_AXI_BRESP	: out std_logic_vector(1 downto 0);
		S_AXI_BVALID	: out std_logic;
		S_AXI_BREADY	: in std_logic;
		S_AXI_ARADDR	: in std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0);
		S_AXI_ARPROT	: in std_logic_vector(2 downto 0);
		S_AXI_ARVALID	: in std_logic;
		S_AXI_ARREADY	: out std_logic;
		S_AXI_RDATA	: out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
		S_AXI_RRESP	: out std_logic_vector(1 downto 0);
		S_AXI_RVALID	: out std_logic;
		S_AXI_RREADY	: in std_logic;
		dbg	: out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0)
		
	);
end frame_grid_top;

architecture implementation of frame_grid_top is  
    ATTRIBUTE X_INTERFACE_INFO : STRING;
    ATTRIBUTE X_INTERFACE_INFO of addr: SIGNAL is "xilinx.com:interface:bram:1.0 BRAM_PORT ADDR";
    ATTRIBUTE X_INTERFACE_INFO of clko: SIGNAL is "xilinx.com:interface:bram:1.0 BRAM_PORT CLK";
    ATTRIBUTE X_INTERFACE_INFO of data: SIGNAL is "xilinx.com:interface:bram:1.0 BRAM_PORT DOUT";
    ATTRIBUTE X_INTERFACE_INFO of eno: SIGNAL is "xilinx.com:interface:bram:1.0 BRAM_PORT EN";
    ATTRIBUTE X_INTERFACE_INFO of rsto: SIGNAL is "xilinx.com:interface:bram:1.0 BRAM_PORT RST";
    
    ATTRIBUTE X_INTERFACE_PARAMETER : STRING;
    ATTRIBUTE X_INTERFACE_PARAMETER of addr: SIGNAL is "MASTER_TYPE BRAM_CTRL, MEM_ECC NONE, MEM_SIZE 524288, MEM_WIDTH 64, READ_LATENCY 1, READ_WRITE_MODE READ_WRITE";
    ATTRIBUTE X_INTERFACE_PARAMETER of clko: SIGNAL is "MASTER_TYPE BRAM_CTRL, MEM_ECC NONE, MEM_SIZE 524288, MEM_WIDTH 64, READ_LATENCY 1, READ_WRITE_MODE READ_WRITE";
    ATTRIBUTE X_INTERFACE_PARAMETER of data: SIGNAL is "MASTER_TYPE BRAM_CTRL, MEM_ECC NONE, MEM_SIZE 524288, MEM_WIDTH 64, READ_LATENCY 1, READ_WRITE_MODE READ_WRITE";
    ATTRIBUTE X_INTERFACE_PARAMETER of eno: SIGNAL is "MASTER_TYPE BRAM_CTRL, MEM_ECC NONE, MEM_SIZE 524288, MEM_WIDTH 64, READ_LATENCY 1, READ_WRITE_MODE READ_WRITE";
    ATTRIBUTE X_INTERFACE_PARAMETER of rsto: SIGNAL is "MASTER_TYPE BRAM_CTRL, MEM_ECC NONE, MEM_SIZE 524288, MEM_WIDTH 64, READ_LATENCY 1, READ_WRITE_MODE READ_WRITE";


    component S_AXI_Lite is 
    generic (
    
		C_S_AXI_DATA_WIDTH	: integer	:= 32;
		
		C_S_AXI_ADDR_WIDTH	: integer	:= 4
        );
	port (
		-- Users to add ports here
        reg0 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
        reg1 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
        reg2 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
        reg3 : out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
		S_AXI_ACLK	: in std_logic;
		S_AXI_ARESETN	: in std_logic;
		S_AXI_AWADDR	: in std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0);
		S_AXI_AWPROT	: in std_logic_vector(2 downto 0);
		S_AXI_AWVALID	: in std_logic;
		S_AXI_AWREADY	: out std_logic;
		S_AXI_WDATA	: in std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
		S_AXI_WSTRB	: in std_logic_vector((C_S_AXI_DATA_WIDTH/8)-1 downto 0);
		S_AXI_WVALID	: in std_logic;
		S_AXI_WREADY	: out std_logic;
		S_AXI_BRESP	: out std_logic_vector(1 downto 0);
		S_AXI_BVALID	: out std_logic;
		S_AXI_BREADY	: in std_logic;
		S_AXI_ARADDR	: in std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0);
		S_AXI_ARPROT	: in std_logic_vector(2 downto 0);
		S_AXI_ARVALID	: in std_logic;
		S_AXI_ARREADY	: out std_logic;
		S_AXI_RDATA	: out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
		S_AXI_RRESP	: out std_logic_vector(1 downto 0);
		S_AXI_RVALID	: out std_logic;
		S_AXI_RREADY	: in std_logic
	);
	end component;
	
	component M_AXIS is 
    generic (
    
		C_M_AXIS_DATA_WIDTH	: integer	:= 128;
		C_M_AXIS_DATA_IDX_WIDTH	: integer	:= 32;
		C_M_AXIS_START_COUNT	: integer	:= 0
        );
	port (
        DATA_TX : in std_logic_vector(C_M_AXIS_DATA_WIDTH-1 downto 0);
        DATA_IDX : out std_logic_vector(C_M_AXIS_DATA_IDX_WIDTH-1 downto 0);
        ENB : in std_logic;
        LAST : in std_logic;
		ACLK	: in std_logic;
		ARESETN	: in std_logic; 
		M_AXIS_TVALID	: out std_logic;
		M_AXIS_TDATA	: out std_logic_vector(C_M_AXIS_DATA_WIDTH-1 downto 0);
		M_AXIS_TSTRB	: out std_logic_vector((C_M_AXIS_DATA_WIDTH/8)-1 downto 0);
		M_AXIS_TLAST	: out std_logic;
		M_AXIS_TREADY	: in std_logic
	);
	end component;
	
	signal address : std_logic_vector(31 downto 0);
	signal size : std_logic_vector(31 downto 0);
	signal enable : std_logic;
	signal enb : std_logic;
	signal last : std_logic;
    signal data_tx : std_logic_vector(C_M_AXIS_DATA_WIDTH-1 downto 0);
    signal data_idx : std_logic_vector(C_M_AXIS_DATA_IDX_WIDTH-1 downto 0);
    signal last_size : std_logic_vector(31 downto 0);
    
    type state_type is (IDLE_STATE, RUN_STATE, END_STATE);
    signal current_state, next_state : state_type;
    
    signal debug_value : std_logic_vector(31 downto 0);
    
                               
begin
    s_axis_port : S_AXI_Lite
        generic map (
            C_S_AXI_DATA_WIDTH => 32,
            C_S_AXI_ADDR_WIDTH => 4
        )
        port map (
            reg0 => address,
            reg1 => size,
            reg2 => reg2,
            reg3 => reg3,
            S_AXI_ACLK => S_AXI_ACLK,
            S_AXI_ARESETN => S_AXI_ARESETN,
            S_AXI_AWADDR => S_AXI_AWADDR,
            S_AXI_AWPROT => S_AXI_AWPROT,
            S_AXI_AWVALID => S_AXI_AWVALID,
            S_AXI_AWREADY => S_AXI_AWREADY,
            S_AXI_WDATA => S_AXI_WDATA,
            S_AXI_WSTRB => S_AXI_WSTRB,
            S_AXI_WVALID => S_AXI_WVALID,
            S_AXI_WREADY => S_AXI_WREADY,
            S_AXI_BRESP => S_AXI_BRESP,
            S_AXI_BVALID => S_AXI_BVALID,
            S_AXI_BREADY => S_AXI_BREADY,
            S_AXI_ARADDR => S_AXI_ARADDR,
            S_AXI_ARPROT => S_AXI_ARPROT,
            S_AXI_ARVALID => S_AXI_ARVALID,
            S_AXI_ARREADY => S_AXI_ARREADY,
            S_AXI_RDATA => S_AXI_RDATA,
            S_AXI_RRESP => S_AXI_RRESP,
            S_AXI_RVALID => S_AXI_RVALID,
            S_AXI_RREADY => S_AXI_RREADY
        );
        
    m_axis_port : M_AXIS
        generic map (
		  C_M_AXIS_DATA_WIDTH => 128,
		  C_M_AXIS_DATA_IDX_WIDTH => 32,
		  C_M_AXIS_START_COUNT => 0
        )
        port map (
          DATA_TX => data_tx,
          DATA_IDX => data_idx,
          ENB  => enb,
          LAST  => last,
		  ACLK	=> ACLK,
		  ARESETN	=> ARESETN, 
		  M_AXIS_TVALID	=> M_AXIS_TVALID,
		  M_AXIS_TDATA	=> M_AXIS_TDATA,
		  M_AXIS_TSTRB	=> M_AXIS_TSTRB,
		  M_AXIS_TLAST	=> M_AXIS_TLAST,
		  M_AXIS_TREADY	=> M_AXIS_TREADY
        );
        
        
    process(ACLK, ARESETN)
    begin
        if ARESETN = '0' then
            current_state <= IDLE_STATE;
        elsif rising_edge(ACLK) then
            current_state <= next_state;
        end if;
    end process;
    
        
        
    process(ACLK, data_idx, current_state, address, size)
    begin              
	if rising_edge(ACLK) then                    
        case current_state is
            when IDLE_STATE =>
                last_size <= (others => '0');
                enable <= '0';
                addr <= (others => '0');
	            enb <= '0';
                last <= '0';
                debug_value <= x"00000000";
            --New state
                if (size > x"00000000") then
                    last_size <= size;
                    next_state <= RUN_STATE;                                                             
                else                                                                                    
                    next_state <= IDLE_STATE;                                                        
                end if;                                                                                 
                        
            when RUN_STATE =>
                debug_value <= x"00000001";
	           enb <= '1';
	           addr <= std_logic_vector(unsigned(address) + shift_left(unsigned(data_idx),4));
               enable <=  '1';
               data_tx <= data;
            --New state
               if (unsigned(shift_left(unsigned(data_idx),4)) >= (shift_right((unsigned(size) - 16), 2))) then 
                  last <= '1';
                  next_state <= END_STATE;
               else
                  next_state <= RUN_STATE;
               end if;
               
            when END_STATE => 
                debug_value <= x"00000002";
               enable <= '0';
               addr <= (others => '0');
	           enb <= '0';
               last <= '0';
               last <= '0';
            --New state
               if (size /= last_size) then 
                  next_state <= IDLE_STATE;
               end if;

                
            when others =>
                next_state <= IDLE_STATE;
        end case;
    end if;
    end process;
                
                                   
	--if (rising_edge (ACLK)) then  
	--   if( ARESETN = '0' or size = x"00000000") then
    --        enable <= '0';
    --        addr <= (others => '0');
	--        enb <= '0';
    --        last <= '0';
    --   -- Each data_idx is multiply by 16, due each transmission is 128 bits. 
    --   -- Size unit is byte, but each memory word is 32 bits.  
	--   elsif (unsigned(shift_left(unsigned(data_idx),4)) >= (shift_right(unsigned(size), 2))) then 
	--        enb <= '1';
	--        addr <= std_logic_vector(unsigned(address) + shift_left(unsigned(data_idx),4));
    --        enable <= '1';
    --        data_tx <= data;
    --        last <= '1';
	--   else
	--        enb <= '1';
	--        addr <= std_logic_vector(unsigned(address) + shift_left(unsigned(data_idx),4));
    --        enable <=  '1';
    --        data_tx <= data;
	--   end if;	
    --end if;
    --end process;
    dbg <= debug_value;
    eno <= enable;
    clko <= ACLK;
    rsto <= not ARESETN;
    
end implementation;