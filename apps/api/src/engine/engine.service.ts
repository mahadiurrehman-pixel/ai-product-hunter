import { Injectable, InternalServerErrorException, Logger } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

@Injectable()
export class EngineService {
  private readonly logger = new Logger(EngineService.name);
  private readonly engineUrl: string;
  private readonly internalSecret: string;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.engineUrl = this.configService.get<string>('ENGINE_URL', 'http://localhost:8000');
    this.internalSecret = this.configService.get<string>('INTERNAL_AUTH_SECRET', '');
  }

  private getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'X-INTERNAL-AUTH': this.internalSecret,
    };
  }

  async runPipeline(query: string, marketplace: string, limit: number, minMatchScore: number): Promise<any> {
    const url = `${this.engineUrl}/internal/pipeline/analyze`;
    try {
      const response = await firstValueFrom(
        this.httpService.post(
          url,
          { query, marketplace, limit, min_match_score: minMatchScore },
          { headers: this.getHeaders() },
        ),
      );
      return response.data;
    } catch (error: any) {
      const errMsg = error instanceof Error ? error.message : String(error);
      this.logger.error(`Failed calling Python Pipeline API: ${errMsg}`);
      throw new InternalServerErrorException('Product matching engine currently unavailable');
    }
  }

  async calculateProfit(calcData: any): Promise<any> {
    const url = `${this.engineUrl}/internal/profit/calculate`;
    try {
      const response = await firstValueFrom(
        this.httpService.post(url, calcData, { headers: this.getHeaders() }),
      );
      return response.data;
    } catch (error: any) {
      const errMsg = error instanceof Error ? error.message : String(error);
      this.logger.error(`Failed calling Python Profit Calculator: ${errMsg}`);
      throw new InternalServerErrorException('Profit calculation engine failed');
    }
  }
}