library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity M_AXIS_tb is
end M_AXIS_tb;

architecture testbench of M_AXIS_tb is
    constant CLK_PERIOD : time := 1 ns; -- Clock period
    signal m_axis_aclk        : std_logic := '0';
    signal m_axis_aresetn     : std_logic := '0';
    signal m_axis_tvalid      : std_logic;
    signal m_axis_tdata       : std_logic_vector(63 downto 0);
    signal m_axis_tstrb       : std_logic_vector(7 downto 0);
    signal m_axis_tlast       : std_logic;
    signal m_axis_tready      : std_logic := '0';
    signal data       : std_logic_vector(63 downto 0);
    signal addr       : std_logic_vector(31 downto 0);
    signal enb       : std_logic;
    signal last       : std_logic;

begin
    uut: entity work.M_AXIS
        generic map (
            C_M_AXIS_DATA_WIDTH    => 64,
            C_M_AXIS_DATA_IDX_WIDTH    => 32,
            C_M_AXIS_START_COUNT    => 0
        )
        port map (
            data_tx => data,
            data_idx => addr,
            enb => enb,
            last => last,
            aclk        => m_axis_aclk,
            aresetn     => m_axis_aresetn,
            m_axis_tvalid      => m_axis_tvalid,
            m_axis_tdata       => m_axis_tdata,
            m_axis_tstrb       => m_axis_tstrb,
            m_axis_tlast       => m_axis_tlast,
            m_axis_tready      => m_axis_tready
        );

    -- Generación de reloj
    process
    variable counter : integer := 0;
    begin
        while now < 1 ms loop
            m_axis_aclk <= '0';
            wait for CLK_PERIOD / 2;
            m_axis_aclk <= '1';
            data <= std_logic_vector(to_unsigned(counter,64));
            counter := counter + 1;
            wait for CLK_PERIOD / 2;
        end loop;
        wait;
    end process;

    -- Proceso de estimulación
    process
    begin
        -- Reset inicial
        m_axis_aresetn <= '0';
        last <= '0';
        enb <= '1';
        wait for 100 ns;
        m_axis_aresetn <= '1';
        m_axis_tready <= '1';
        wait for 500 us;
        last <= '1';

        -- Simulación de transacciones aquí...
        wait for 1 ms;
        wait;
    end process;
end testbench;