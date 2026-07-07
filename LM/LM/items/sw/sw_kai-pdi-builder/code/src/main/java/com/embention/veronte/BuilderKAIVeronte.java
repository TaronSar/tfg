package com.embention.veronte;

import com.embention.board.ProductController;
import com.embention.common.file.LogMgrDevice;
import com.embention.core.guifx.board.Board;
import com.embention.guifx.util.AppTitleHelper;
import com.embention.veronte.gui.BoardKAIVeronte;
import com.embention.veronte.net.config.LConfigMgr;
import files.FilesMgr;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.stage.Stage;

public class BuilderKAIVeronte extends Application {
  private final Board board = new BoardKAIVeronte();
  private final static Logger log = Logger.getLogger(BuilderKAIVeronte.class.getSimpleName());
  private final ProductController productController = new ProductController(board,
      new Image(BuilderKAIVeronte.class.getResourceAsStream("KAIVerontePDIBuilderTitle.png")),
      FilesMgr.LOG_FILE_VERONTE_B);

  ScheduledExecutorService exe = Executors.newScheduledThreadPool(1);

  @Override
  public void start(Stage primaryStage) throws Exception {
    try {
      LConfigMgr.getInstance().setCfgFolder(FilesMgr.URL_VER_B_CONFIG_FOLDER);
      LogMgrDevice.create(FilesMgr.LOG_FILE_VERONTE_B);
      Locale.setDefault(Locale.ENGLISH);
      String appName = AppTitleHelper.setTitle(primaryStage);
      primaryStage.setScene(new Scene((Parent) productController.getNode()));
      primaryStage.getIcons().add(new Image(BuilderKAIVeronte.class.getResourceAsStream("KAIVerontePDIBuilderIcon.png")));
      primaryStage.setWidth(600);
      primaryStage.setHeight(400);
      primaryStage.setResizable(false);
      log.log(Level.INFO, "Start " + appName + " version: " + SystemBaseVersion.CURRENT);
      primaryStage.show();
      exe.scheduleAtFixedRate(System::gc, 0, 10, TimeUnit.SECONDS);
    }catch (Throwable e) {
      log.severe(e.getMessage());
      e.printStackTrace();
    }
  }

  @Override
  public void stop() {
    exe.close();
    Platform.exit();
    System.exit(0);
  }

  public static void main(String[] args) {
    launch(args);
  }
}
